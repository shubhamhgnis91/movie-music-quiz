# main.py
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
import sqlite3
import random

app = FastAPI()

# --- WebSocket and Pydantic Models (No changes) ---

class Guess(BaseModel):
    song_id: int
    guess_text: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- Helper function for the new JioSaavn API Logic ---

async def search_jiosaavn(term: str):
    """
    Searches JioSaavn in a two-step process:
    1. Search for an album by the movie title.
    2. Get the details of the first album found, which includes its songs.
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Search for the album to get its ID
        search_url = "https://saavn.dev/api/search/albums"
        search_params = {"query": term, "limit": 1}
        search_response = await client.get(search_url, params=search_params)
        
        if search_response.status_code != 200:
            return []

        search_data = search_response.json()
        if not search_data.get("data", {}).get("results"):
            return []
            
        album_id = search_data["data"]["results"][0].get("id")
        if not album_id:
            return []

        # Step 2: Get the album details using the ID
        album_url = "https://saavn.dev/api/albums"
        album_params = {"id": album_id}
        album_response = await client.get(album_url, params=album_params)

        if album_response.status_code != 200:
            return []
            
        album_data = album_response.json()
        return album_data.get("data", {}).get("songs", [])

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")

@app.get("/get_quiz_song")
async def get_quiz_song():
    """
    Gets a random song for the quiz using the JioSaavn API.
    """
    for _ in range(20): # Try up to 20 times
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        cursor.execute("SELECT title FROM movies ORDER BY RANDOM() LIMIT 1")
        result = cursor.fetchone()
        connection.close()

        if result:
            movie_title = result[0]
            print(f"--- Attempting search for: {movie_title} ---")
            
            songs = await search_jiosaavn(movie_title)
            
            if songs:
                chosen_song = random.choice(songs)
                
                # Find the best quality download URL (320kbps)
                best_url = ""
                for link in chosen_song.get("downloadUrl", []):
                    if link.get("quality") == "320kbps":
                        best_url = link.get("url")
                        break
                
                if best_url:
                    return {
                        "title": chosen_song.get("name"),
                        "movie": chosen_song.get("album", {}).get("name"),
                        "preview_url": best_url
                    }
    
    raise HTTPException(status_code=500, detail="Could not find a valid song after multiple attempts.")