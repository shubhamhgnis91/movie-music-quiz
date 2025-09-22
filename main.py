import asyncio
import json
import random
import sqlite3
import uuid
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Add CORS middleware for better compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Pydantic Models for API Requests
# --------------------------------------------------------------------------

class CreateRoomRequest(BaseModel):
    host_name: str
    password: Optional[str] = None

class Player(BaseModel):
    id: int
    name: str
    is_ready: bool = False

# --------------------------------------------------------------------------
# Game State and Room Management
# --------------------------------------------------------------------------

class GameState:
    """Manages the state of a single game room."""
    def __init__(self, room_id: str, host_id: int, host_name: str, password: Optional[str] = None):
        self.room_id: str = room_id
        self.host_id: int = host_id
        self.password: Optional[str] = password
        self.players: Dict[int, Player] = {host_id: Player(id=host_id, name=host_name)}
        self.scores: Dict[int, int] = {}
        self.current_round: int = 0
        self.total_rounds: int = 10
        self.current_song: Optional[Dict] = None
        self.players_who_guessed: set[int] = set()
        self.is_game_active: bool = False
        self.game_loop_task: Optional[asyncio.Task] = None

    def add_player(self, player_id: int, player_name: str):
        if player_id not in self.players:
            self.players[player_id] = Player(id=player_id, name=player_name)

    def remove_player(self, player_id: int):
        if player_id in self.players:
            del self.players[player_id]
        if player_id in self.scores:
            del self.scores[player_id]
    
    def set_player_ready(self, player_id: int, is_ready: bool):
        if player_id in self.players:
            self.players[player_id].is_ready = is_ready

    def start_game(self):
        """Initializes scores for all players and starts the game."""
        self.is_game_active = True
        self.current_round = 0
        self.scores = {player_id: 0 for player_id in self.players}
        self.players_who_guessed.clear()

    def check_guess(self, player_id: int, guess_text: str):
        if player_id in self.players_who_guessed: 
            return None
        if player_id not in self.scores: 
            self.scores[player_id] = 0
        self.players_who_guessed.add(player_id)
        correct_answer = self.current_song.get("movie", "").lower() if self.current_song else ""
        if guess_text.lower() == correct_answer:
            self.scores[player_id] += 10
            return True
        return False

    def get_full_state(self) -> Dict:
        """Returns a dictionary representing the complete state of the room."""
        current_song_info = None
        if self.current_song:
            current_song_info = {"preview_url": self.current_song.get("preview_url")}

        return {
            "room_id": self.room_id,
            "host_id": self.host_id,
            "players": [player.dict() for player in self.players.values()],
            "is_game_active": self.is_game_active,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "current_song": current_song_info,
            "scores": self.scores
        }

class GameRoomManager:
    """Manages all active game rooms on the server."""
    def __init__(self):
        self.rooms: Dict[str, GameState] = {}

    def create_room(self, host_id: int, host_name: str, password: Optional[str] = None) -> GameState:
        room_id = str(uuid.uuid4())[:6].upper()
        room = GameState(room_id, host_id, host_name, password)
        self.rooms[room_id] = room
        print(f"Room created: {room_id} for host {host_name}")
        return room

    def get_room(self, room_id: str) -> Optional[GameState]:
        return self.rooms.get(room_id)

    def get_public_rooms(self) -> List[Dict]:
        return [
            {
                "room_id": room.room_id, 
                "host_name": room.players[room.host_id].name, 
                "player_count": len(room.players)
            }
            for room in self.rooms.values() 
            if not room.password and not room.is_game_active
        ]

room_manager = GameRoomManager()

# --------------------------------------------------------------------------
# Data Fetching Logic
# --------------------------------------------------------------------------
async def search_jiosaavn(term: str):
    async with httpx.AsyncClient() as client:
        search_url = "https://saavn.dev/api/search/albums"
        search_params = {"query": term, "limit": 1}
        try:
            search_response = await client.get(search_url, params=search_params, timeout=10.0)
            search_response.raise_for_status()
            search_data = search_response.json()
        except Exception as e:
            print(f"Search error for {term}: {e}")
            return []
        
        if not search_data.get("data", {}).get("results"): 
            return []
        
        album_id = search_data["data"]["results"][0].get("id")
        if not album_id: 
            return []
        
        album_url = "https://saavn.dev/api/albums"
        album_params = {"id": album_id}
        try:
            album_response = await client.get(album_url, params=album_params, timeout=10.0)
            album_response.raise_for_status()
            album_data = album_response.json()
        except Exception as e:
            print(f"Album fetch error: {e}")
            return []
        
        return album_data.get("data", {}).get("songs", [])

async def get_movie_suggestions(query: str) -> List[str]:
    """Get movie title suggestions from database for autocomplete."""
    if not query or len(query) < 2:
        return []
    
    try:
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        # Search for movies that start with or contain the query
        cursor.execute(
            "SELECT DISTINCT title FROM movies WHERE LOWER(title) LIKE LOWER(?) LIMIT 10",
            (f"%{query}%",)
        )
        results = cursor.fetchall()
        connection.close()
        return [result[0] for result in results]
    except Exception as e:
        print(f"Error getting suggestions: {e}")
        return []

async def get_quiz_song():
    # Check if database exists
    try:
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='movies'")
        if cursor.fetchone()[0] == 0:
            # Create dummy data if table doesn't exist
            cursor.execute("CREATE TABLE IF NOT EXISTS movies (title TEXT)")
            cursor.execute("INSERT INTO movies (title) VALUES ('Dangal'), ('3 Idiots'), ('PK'), ('Baahubali'), ('Dhoom'), ('Sholay'), ('DDLJ'), ('Lagaan'), ('Kabhi Khushi Kabhie Gham'), ('Kuch Kuch Hota Hai')")
            connection.commit()
        connection.close()
    except Exception as e:
        print(f"Database error: {e}")
        # Return dummy song if database fails
        return {
            "title": "Demo Song",
            "movie": "Demo Movie",
            "preview_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        }
    
    for _ in range(20):
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        cursor.execute("SELECT title FROM movies ORDER BY RANDOM() LIMIT 1")
        result = cursor.fetchone()
        connection.close()
        
        if result:
            movie_title = result[0]
            songs = await search_jiosaavn(movie_title)
            if songs:
                chosen_song = random.choice(songs)
                best_url = ""
                for link in chosen_song.get("downloadUrl", []):
                    if link.get("quality") == "320kbps": 
                        best_url = link.get("url")
                        break
                if best_url:
                    return {
                        "title": chosen_song.get("name"), 
                        "movie": movie_title, 
                        "preview_url": best_url
                    }
    
    # Return demo song if no valid songs found
    return {
        "title": "Demo Song",
        "movie": "Demo Movie", 
        "preview_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    }

# --------------------------------------------------------------------------
# Game Loop & WebSocket Communication
# --------------------------------------------------------------------------
connections: Dict[str, Dict[int, WebSocket]] = {}

async def broadcast_message(room_id: str, message: dict):
    if room_id in connections:
        disconnected = []
        for client_id, ws in connections[room_id].items():
            try: 
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"Failed to send to client {client_id}: {e}")
                disconnected.append(client_id)
        # Clean up disconnected clients
        for client_id in disconnected:
            del connections[room_id][client_id]

async def broadcast_room_state(room_id: str):
    room = room_manager.get_room(room_id)
    if room: 
        await broadcast_message(room_id, {"action": "update_state", "state": room.get_full_state()})

async def game_loop(room_id: str):
    room = room_manager.get_room(room_id)
    if not room: 
        return
    
    while room.current_round < room.total_rounds and room.is_game_active:
        try:
            song_data = await get_quiz_song()
            room.current_song = song_data
            room.current_round += 1
            room.players_who_guessed.clear()  # Clear guesses for new round
            
            # Announce new round
            await broadcast_message(room_id, {
                "action": "chat_message",
                "player_name": "System",
                "text": f"🎵 Round {room.current_round}/{room.total_rounds} starting! Listen carefully..."
            })
            
            await broadcast_room_state(room_id)
            
            # Wait for 30 seconds of playing
            await asyncio.sleep(30)
            
            if not room.is_game_active: 
                break
            
            # Stop the music and reveal answer
            await broadcast_message(room_id, {
                "action": "round_end", 
                "correct_answer": room.current_song.get("movie"), 
                "scores": room.scores
            })
            
            # Send round results to chat
            correct_answer = room.current_song.get("movie", "Unknown")
            await broadcast_message(room_id, {
                "action": "chat_message",
                "player_name": "System",
                "text": f"⏰ Time's up! The correct answer was: {correct_answer}"
            })
            
            # List who guessed correctly
            correct_guessers = []
            for pid in room.players_who_guessed:
                if pid in room.scores and room.scores[pid] > 0:
                    player_name = room.players.get(pid).name if pid in room.players else "Unknown"
                    correct_guessers.append(player_name)
            
            if correct_guessers:
                await broadcast_message(room_id, {
                    "action": "chat_message",
                    "player_name": "System",
                    "text": f"✅ Correct guesses by: {', '.join(correct_guessers)}"
                })
            else:
                await broadcast_message(room_id, {
                    "action": "chat_message",
                    "player_name": "System",
                    "text": "❌ Nobody guessed correctly this round!"
                })
            
            # Update scoreboard
            await broadcast_room_state(room_id)
            
            # Wait before next round
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error in game loop: {e}")
            break
    
    room.is_game_active = False
    
    # Game over - announce winner
    if room.scores:
        winner_id = max(room.scores, key=room.scores.get)
        winner_name = room.players.get(winner_id).name if winner_id in room.players else "Unknown"
        winner_score = room.scores[winner_id]
        
        await broadcast_message(room_id, {
            "action": "chat_message",
            "player_name": "System",
            "text": f"🏆 Game Over! Winner: {winner_name} with {winner_score} points!"
        })
    
    await broadcast_message(room_id, {"action": "game_over", "leaderboard": room.scores})
    print(f"Game in room {room_id} has ended.")

# --------------------------------------------------------------------------
# FastAPI Endpoints
# --------------------------------------------------------------------------
@app.get("/")
async def get_homepage():
    return FileResponse("static/index.html")

@app.get("/api/rooms")
async def list_public_rooms():
    return room_manager.get_public_rooms()

@app.post("/api/rooms")
async def create_room_api(request: CreateRoomRequest):
    client_id = random.randint(10000, 99999)
    room = room_manager.create_room(client_id, request.host_name, request.password)
    return {"room_id": room.room_id, "host_id": client_id}

@app.websocket("/ws/{room_id}/{client_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: int, player_name: str):
    # IMPORTANT: Accept the WebSocket connection first!
    await websocket.accept()
    
    print(f"WebSocket connection attempt: room={room_id}, client={client_id}, player={player_name}")
    
    room = room_manager.get_room(room_id)
    if not room:
        print(f"Room {room_id} not found")
        await websocket.send_text(json.dumps({"action": "error", "message": "Room not found"}))
        await websocket.close(code=1008, reason="Room not found")
        return
    
    # Initialize room connections dict if needed
    if room_id not in connections:
        connections[room_id] = {}
    
    connections[room_id][client_id] = websocket
    room.add_player(client_id, player_name)
    
    print(f"Player {player_name} (ID: {client_id}) joined room {room_id}")
    await broadcast_room_state(room_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")
            
            print(f"Received action '{action}' from player {client_id}")

            if action == "set_ready":
                room.set_player_ready(client_id, message.get("is_ready", False))
                await broadcast_room_state(room_id)
                
            elif action == "kick_player" and client_id == room.host_id:
                player_to_kick = message.get("player_id")
                if player_to_kick in connections.get(room_id, {}):
                    await connections[room_id][player_to_kick].close(code=1000, reason="Kicked by host")
                room.remove_player(player_to_kick)
                await broadcast_room_state(room_id)
                
            elif action == "start_game" and client_id == room.host_id and not room.is_game_active:
                room.start_game()
                room.game_loop_task = asyncio.create_task(game_loop(room_id))
                await broadcast_room_state(room_id)
                
            elif action == "guess" and room.is_game_active:
                guess_correct = room.check_guess(client_id, message.get("text", ""))
                if guess_correct is not None:
                    await broadcast_message(room_id, {
                        "action": "guess_result", 
                        "player_name": player_name, 
                        "correct": guess_correct
                    })
                    
                    # Send guess result to chat
                    if guess_correct:
                        await broadcast_message(room_id, {
                            "action": "chat_message",
                            "player_name": "System",
                            "text": f"✅ {player_name} guessed correctly!"
                        })
                    else:
                        await broadcast_message(room_id, {
                            "action": "chat_message",
                            "player_name": "System",
                            "text": f"❌ {player_name} guessed wrong!"
                        })
                    
                    await broadcast_room_state(room_id)
                    
            elif action == "chat":
                await broadcast_message(room_id, {
                    "action": "chat_message",
                    "player_name": player_name,
                    "text": message.get("text", "")
                })
                
            elif action == "get_suggestions":
                # Send autocomplete suggestions for movie names
                query = message.get("query", "")
                suggestions = await get_movie_suggestions(query)
                await websocket.send_text(json.dumps({
                    "action": "suggestions",
                    "suggestions": suggestions
                }))
            
    except WebSocketDisconnect:
        print(f"Player {player_name} (ID: {client_id}) disconnected from room {room_id}")
    except Exception as e:
        print(f"Error handling WebSocket for client {client_id}: {e}")
    finally:
        # Clean up on disconnect
        room.remove_player(client_id)
        if client_id in connections.get(room_id, {}):
            del connections[room_id][client_id]
        
        if len(room.players) == 0:
            print(f"Room {room_id} is empty, closing.")
            if room.game_loop_task and not room.game_loop_task.done():
                room.game_loop_task.cancel()
            if room_id in room_manager.rooms:
                del room_manager.rooms[room_id]
            if room_id in connections:
                del connections[room_id]
        else:
            await broadcast_room_state(room_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)