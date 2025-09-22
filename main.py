import asyncio
import csv
import json
import os
import random
import sqlite3
import uuid
import time
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
# Database Initialization
# --------------------------------------------------------------------------

def initialize_database():
    """Initialize the database with movie data on startup"""
    try:
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        
        # Check if table exists and has data
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='movies'")
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM movies")
            row_count = cursor.fetchone()[0]
            if row_count > 0:
                print(f"Database already initialized with {row_count} movies")
                connection.close()
                return
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                title TEXT NOT NULL
            )
        """)
        
        print("Initializing database with movie data...")
        
        # Try to read from CSV file first
        movies_added = 0
        try:
            with open('top500.csv', 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=',')
                next(reader)  # Skip header row
                
                for row in reader:
                    if len(row) > 1:  # Make sure row has enough columns
                        title = row[1].strip()  # Movie title is in 2nd column
                        if title:  # Only add non-empty titles
                            cursor.execute("INSERT INTO movies (title) VALUES (?)", (title,))
                            movies_added += 1
                            
            print(f"Successfully added {movies_added} movies from CSV file")
            
        except FileNotFoundError:
            print("CSV file not found, adding fallback movies...")
            # Fallback movie list if CSV is not available
            fallback_movies = [
                'Dangal', '3 Idiots', 'PK', 'Baahubali', 'Dhoom', 'Sholay', 'DDLJ', 'Lagaan',
                'Kabhi Khushi Kabhie Gham', 'Kuch Kuch Hota Hai', 'Zindagi Na Milegi Dobara',
                'Queen', 'Andhadhun', 'Article 15', 'Uri', 'Mission Mangal', 'Chhichhore',
                'Badhaai Ho', 'Stree', 'Dream Girl', 'Housefull', 'Golmaal', 'Dhamaal',
                'Welcome', 'Hera Pheri', 'Munna Bhai MBBS', 'Chak De India', 'Taare Zameen Par',
                'My Name is Khan', 'Chennai Express', 'Happy New Year', 'Bajrangi Bhaijaan',
                'Sultan', 'Tiger Zinda Hai', 'Padmaavat', 'Simmba', 'Kesari', 'Good Newwz'
            ]
            
            for movie in fallback_movies:
                cursor.execute("INSERT INTO movies (title) VALUES (?)", (movie,))
                movies_added += 1
                
            print(f"Added {movies_added} fallback movies")
        
        connection.commit()
        connection.close()
        print("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        # Continue without database - the app will use demo songs

# Initialize database on startup
initialize_database()

# --------------------------------------------------------------------------
# Pydantic Models for API Requests
# --------------------------------------------------------------------------

class CreateRoomRequest(BaseModel):
    host_name: str
    password: Optional[str] = None

class GameSettings(BaseModel):
    total_rounds: int = 10
    music_duration: int = 30  # seconds
    game_type: str = "regular"  # "regular" or "speed"

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
        self.music_duration: int = 30
        self.game_type: str = "regular"
        self.current_song: Optional[Dict] = None
        self.players_who_guessed: set[int] = set()
        self.guess_times: Dict[int, float] = {}  # For speed-based scoring
        self.round_start_time: Optional[float] = None
        self.is_game_active: bool = False
        self.is_round_active: bool = False
        self.is_reveal_phase: bool = False  # New phase for showing album image
        self.game_loop_task: Optional[asyncio.Task] = None

    def update_settings(self, settings: GameSettings):
        """Update game settings (only allowed before game starts)"""
        if not self.is_game_active:
            self.total_rounds = settings.total_rounds
            self.music_duration = settings.music_duration
            self.game_type = settings.game_type
            return True
        return False

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
        self.guess_times.clear()

    def start_round(self):
        """Start a new round"""
        self.is_round_active = True
        self.is_reveal_phase = False
        self.round_start_time = time.time()
        self.players_who_guessed.clear()
        self.guess_times.clear()

    def end_round(self):
        """End the current round"""
        self.is_round_active = False

    def start_reveal_phase(self):
        """Start the reveal phase (show album image)"""
        self.is_round_active = False
        self.is_reveal_phase = True

    def check_guess(self, player_id: int, guess_text: str):
        if not self.is_round_active or player_id in self.players_who_guessed: 
            return None
        
        if player_id not in self.scores: 
            self.scores[player_id] = 0
        
        self.players_who_guessed.add(player_id)
        current_time = time.time()
        self.guess_times[player_id] = current_time - (self.round_start_time or current_time)
        
        correct_answer = self.current_song.get("movie", "").lower() if self.current_song else ""
        if guess_text.lower() == correct_answer:
            if self.game_type == "speed":
                # Speed-based scoring: earlier guesses get more points
                time_elapsed = self.guess_times[player_id]
                max_points = 20
                min_points = 5
                # Calculate points based on speed (faster = more points)
                points = max(min_points, max_points - int(time_elapsed * 2))
                self.scores[player_id] += points
            else:
                # Regular scoring: fixed points for correct answers
                self.scores[player_id] += 10
            return True
        return False

    def get_full_state(self) -> Dict:
        """Returns a dictionary representing the complete state of the room."""
        current_song_info = None
        if self.current_song:
            # During round: only send preview_url
            # During reveal: send preview_url and image
            if self.is_reveal_phase:
                current_song_info = {
                    "preview_url": self.current_song.get("preview_url"),
                    "image": self.current_song.get("image"),
                    "title": self.current_song.get("title"),
                    "movie": self.current_song.get("movie")
                }
            else:
                current_song_info = {
                    "preview_url": self.current_song.get("preview_url")
                }

        return {
            "room_id": self.room_id,
            "host_id": self.host_id,
            "players": [player.dict() for player in self.players.values()],
            "is_game_active": self.is_game_active,
            "is_round_active": self.is_round_active,
            "is_reveal_phase": self.is_reveal_phase,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "music_duration": self.music_duration,
            "game_type": self.game_type,
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
    # Try to get from database first
    try:
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
                album_image = ""
                
                # Get the best quality audio URL
                for link in chosen_song.get("downloadUrl", []):
                    if link.get("quality") == "320kbps": 
                        best_url = link.get("url")
                        break
                
                # Get the best quality image
                images = chosen_song.get("image", [])
                if images:
                    # Find the highest quality image (usually "500x500")
                    for img in reversed(images):  # Reverse to get higher quality first
                        if img.get("quality") in ["500x500", "150x150"]:
                            album_image = img.get("url")
                            break
                    # Fallback to first image if no specific quality found
                    if not album_image and images:
                        album_image = images[-1].get("url", "")
                
                if best_url:
                    print(f"Found song: {chosen_song.get('name')} from {movie_title}")
                    return {
                        "title": chosen_song.get("name"), 
                        "movie": movie_title, 
                        "preview_url": best_url,
                        "image": album_image or "https://via.placeholder.com/300x300?text=No+Image"
                    }
    except Exception as e:
        print(f"Database error: {e}")
    
    # Return demo song if database fails or no songs found
    print("Using demo song as fallback")
    return {
        "title": "Demo Song",
        "movie": "Demo Movie", 
        "preview_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "image": "https://via.placeholder.com/300x300?text=Demo+Album"
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
            room.start_round()  # Start the round with timing
            
            # Send game notification (not chat)
            await broadcast_message(room_id, {
                "action": "game_notification",
                "type": "round_start",
                "message": f"🎵 Round {room.current_round}/{room.total_rounds} starting! Listen carefully..."
            })
            
            # Send round start signal
            await broadcast_message(room_id, {
                "action": "round_start"
            })
            
            await broadcast_room_state(room_id)
            
            # Wait for the configured music duration
            await asyncio.sleep(room.music_duration)
            
            if not room.is_game_active: 
                break
            
            # End the guessing phase and start reveal phase
            room.start_reveal_phase()
            
            # Send round end signal with reveal data
            await broadcast_message(room_id, {
                "action": "round_end", 
                "correct_answer": room.current_song.get("movie"), 
                "song_title": room.current_song.get("title"),
                "album_image": room.current_song.get("image"),
                "scores": room.scores
            })
            
            await broadcast_room_state(room_id)  # This will now include the album image
            
            # Send game notification for round end
            correct_answer = room.current_song.get("movie", "Unknown")
            await broadcast_message(room_id, {
                "action": "game_notification",
                "type": "round_end",
                "message": f"⏰ Time's up! The correct answer was: {correct_answer}"
            })
            
            # Send individual guess results as game notifications
            correct_guessers = []
            wrong_guessers = []
            
            for pid in room.players_who_guessed:
                player_obj = room.players.get(pid)
                if player_obj:
                    player_name = player_obj.name
                    # Check if this player got it right by looking at score increase
                    if pid in room.scores and room.scores[pid] > 0:
                        if room.game_type == "speed" and pid in room.guess_times:
                            time_taken = round(room.guess_times[pid], 2)
                            points_earned = max(5, 20 - int(room.guess_times[pid] * 2))
                            correct_guessers.append((player_name, points_earned, time_taken))
                        else:
                            correct_guessers.append((player_name, 10, None))
                    else:
                        wrong_guessers.append(player_name)
            
            # Send correct guesses notification
            if correct_guessers:
                if room.game_type == "speed":
                    guess_details = [f"{name} (+{points} pts, {time}s)" if time else f"{name} (+{points} pts)" 
                                   for name, points, time in correct_guessers]
                else:
                    guess_details = [f"{name} (+{points} pts)" for name, points, time in correct_guessers]
                
                await broadcast_message(room_id, {
                    "action": "game_notification",
                    "type": "correct_guesses",
                    "message": f"✅ Correct: {', '.join(guess_details)}",
                    "correct_players": [name for name, _, _ in correct_guessers]
                })
            
            # Send wrong guesses notification  
            if wrong_guessers:
                await broadcast_message(room_id, {
                    "action": "game_notification",
                    "type": "wrong_guesses",
                    "message": f"❌ Wrong: {', '.join(wrong_guessers)}"
                })
            
            if not correct_guessers and not wrong_guessers:
                await broadcast_message(room_id, {
                    "action": "game_notification",
                    "type": "no_guesses",
                    "message": "🤷 Nobody made a guess this round!"
                })
            
            # Wait before next round (reveal phase duration)
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Error in game loop: {e}")
            break
    
    room.is_game_active = False
    room.end_round()
    
    # Game over - announce winner
    if room.scores:
        winner_id = max(room.scores, key=room.scores.get)
        winner_name = room.players.get(winner_id).name if winner_id in room.players else "Unknown"
        winner_score = room.scores[winner_id]
        
        await broadcast_message(room_id, {
            "action": "game_notification",
            "type": "game_over",
            "message": f"🏆 Game Over! Winner: {winner_name} with {winner_score} points!"
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
                
            elif action == "update_settings" and client_id == room.host_id:
                settings_data = message.get("settings", {})
                try:
                    settings = GameSettings(**settings_data)
                    if room.update_settings(settings):
                        await broadcast_message(room_id, {
                            "action": "settings_updated",
                            "settings": {
                                "total_rounds": room.total_rounds,
                                "music_duration": room.music_duration,
                                "game_type": room.game_type
                            }
                        })
                        await broadcast_room_state(room_id)
                    else:
                        await websocket.send_text(json.dumps({
                            "action": "error",
                            "message": "Cannot change settings during game"
                        }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "action": "error",
                        "message": f"Invalid settings: {str(e)}"
                    }))
                
            elif action == "start_game" and client_id == room.host_id and not room.is_game_active:
                room.start_game()
                room.game_loop_task = asyncio.create_task(game_loop(room_id))
                await broadcast_room_state(room_id)
                
            elif action == "guess" and room.is_game_active and room.is_round_active:
                guess_correct = room.check_guess(client_id, message.get("text", ""))
                if guess_correct is not None:
                    # Calculate points earned for this guess
                    points_earned = 0
                    if guess_correct:
                        if room.game_type == "speed":
                            time_elapsed = room.guess_times.get(client_id, 0)
                            max_points = 20
                            min_points = 5
                            points_earned = max(min_points, max_points - int(time_elapsed * 2))
                        else:
                            points_earned = 10
                    
                    # Send individual guess result (not broadcast)
                    await websocket.send_text(json.dumps({
                        "action": "guess_result", 
                        "correct": guess_correct,
                        "points_earned": points_earned
                    }))
                    
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
    # Use environment variable for port (required for Render)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)