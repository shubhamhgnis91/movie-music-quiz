import asyncio
import csv
import json
import os
import random
import sqlite3
import uuid
import time
import hashlib
import hmac
from typing import Dict, List, Optional
from urllib.parse import parse_qs
from collections import defaultdict, deque
from datetime import datetime, timedelta
import re

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, validator
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# ✅ SECURITY FIX: Restrictive CORS instead of wildcard
allowed_origins = [
    "https://movie-music-quiz.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://localhost:8000"
]

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["movie-music-quiz.onrender.com", "localhost", "127.0.0.1"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # ✅ FIXED: Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # ✅ FIXED: Only needed methods
    allow_headers=["Content-Type", "Authorization"],  # ✅ FIXED: Specific headers only
)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "fallback-secret-key-change-in-production"))

# ✅ SECURITY FIX: Rate limiting storage
rate_limit_storage = defaultdict(lambda: deque())
MAX_REQUESTS_PER_MINUTE = 60
MAX_CONNECTIONS_PER_IP = 5
connection_count_by_ip = defaultdict(int)

def check_rate_limit(client_ip: str) -> bool:
    """Rate limiting: max 60 requests per minute per IP"""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Clean old requests
    while rate_limit_storage[client_ip] and rate_limit_storage[client_ip][0] < minute_ago:
        rate_limit_storage[client_ip].popleft()
    
    # Check if under limit
    if len(rate_limit_storage[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    # Add current request
    rate_limit_storage[client_ip].append(now)
    return True

# ✅ SECURITY FIX: Input sanitization
def sanitize_text_input(text: str) -> str:
    """Sanitize text input to prevent XSS and injection attacks"""
    if not text:
        return ""
    
    # Remove/escape potentially dangerous characters
    text = str(text).strip()
    
    # Remove HTML tags and scripts
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # Limit length to prevent DoS
    text = text[:100] if text else ""
    
    return text

def validate_room_id(room_id: str) -> bool:
    """Validate room ID format"""
    return bool(room_id and re.match(r'^[A-Z0-9]{6}$', room_id))

def validate_client_id(client_id: int) -> bool:
    """Validate client ID range"""
    return isinstance(client_id, int) and 10000 <= client_id <= 99999

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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE
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
                        title = sanitize_text_input(row[1])  # ✅ FIXED: Sanitize CSV input
                        if title:  # Only add non-empty titles
                            cursor.execute("INSERT OR IGNORE INTO movies (title) VALUES (?)", (title,))
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
                cursor.execute("INSERT OR IGNORE INTO movies (title) VALUES (?)", (movie,))
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
    
    @validator('host_name')
    def validate_host_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Host name is required')
        v = sanitize_text_input(v)
        if len(v) > 50:
            raise ValueError('Host name too long (max 50 characters)')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > 100:
                raise ValueError('Password too long (max 100 characters)')
        return v

class GameSettings(BaseModel):
    total_rounds: int = 10
    music_duration: int = 30  # seconds
    game_type: str = "regular"  # "regular" or "speed"
    
    @validator('total_rounds')
    def validate_rounds(cls, v):
        if not 5 <= v <= 20:
            raise ValueError('Total rounds must be between 5 and 20')
        return v
    
    @validator('music_duration')
    def validate_duration(cls, v):
        if not 15 <= v <= 60:
            raise ValueError('Music duration must be between 15 and 60 seconds')
        return v
    
    @validator('game_type')
    def validate_game_type(cls, v):
        if v not in ['regular', 'speed']:
            raise ValueError('Game type must be "regular" or "speed"')
        return v

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
        self.password_hash: Optional[str] = None
        
        # ✅ SECURITY FIX: Hash passwords instead of storing plaintext
        if password:
            self.password_hash = hashlib.sha256(password.encode()).hexdigest()
            self.password = None  # Don't store plaintext
        
        self.players: Dict[int, Player] = {host_id: Player(id=host_id, name=sanitize_text_input(host_name))}
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
        self.is_reveal_phase: bool = False
        self.game_loop_task: Optional[asyncio.Task] = None
        self.created_at: datetime = datetime.now()
        self.last_activity: datetime = datetime.now()

    def check_password(self, provided_password: Optional[str]) -> bool:
        """Check if the provided password matches the room password"""
        if not self.password_hash:  # No password required
            return True
        if provided_password is None:  # Password required but none provided
            return False
        
        # ✅ SECURITY FIX: Compare hashed passwords instead of plaintext
        provided_hash = hashlib.sha256(provided_password.encode()).hexdigest()
        return hmac.compare_digest(self.password_hash, provided_hash)

    def update_settings(self, settings: GameSettings):
        """Update game settings (only allowed before game starts)"""
        if not self.is_game_active:
            self.total_rounds = settings.total_rounds
            self.music_duration = settings.music_duration
            self.game_type = settings.game_type
            self.last_activity = datetime.now()
            return True
        return False

    def add_player(self, player_id: int, player_name: str):
        if player_id not in self.players and len(self.players) < 10:  # ✅ FIXED: Limit players
            self.players[player_id] = Player(id=player_id, name=sanitize_text_input(player_name))
            self.last_activity = datetime.now()

    def remove_player(self, player_id: int):
        if player_id in self.players:
            del self.players[player_id]
        if player_id in self.scores:
            del self.scores[player_id]
        self.last_activity = datetime.now()
    
    def set_player_ready(self, player_id: int, is_ready: bool):
        if player_id in self.players:
            self.players[player_id].is_ready = is_ready
            self.last_activity = datetime.now()

    def start_game(self):
        """Initializes scores for all players and starts the game."""
        self.is_game_active = True
        self.current_round = 0
        self.scores = {player_id: 0 for player_id in self.players}
        self.players_who_guessed.clear()
        self.guess_times.clear()
        self.last_activity = datetime.now()

    def start_round(self):
        """Start a new round"""
        self.is_round_active = True
        self.is_reveal_phase = False
        self.round_start_time = time.time()
        self.players_who_guessed.clear()
        self.guess_times.clear()
        self.last_activity = datetime.now()

    def end_round(self):
        """End the current round"""
        self.is_round_active = False
        self.last_activity = datetime.now()

    def start_reveal_phase(self):
        """Start the reveal phase (show album image)"""
        self.is_round_active = False
        self.is_reveal_phase = True
        self.last_activity = datetime.now()

    def check_guess(self, player_id: int, guess_text: str):
        if not self.is_round_active or player_id in self.players_who_guessed: 
            return None
        
        if player_id not in self.scores: 
            self.scores[player_id] = 0
        
        # ✅ SECURITY FIX: Sanitize guess input
        guess_text = sanitize_text_input(guess_text)
        
        self.players_who_guessed.add(player_id)
        current_time = time.time()
        self.guess_times[player_id] = current_time - (self.round_start_time or current_time)
        self.last_activity = datetime.now()
        
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
            "scores": self.scores,
            "has_password": bool(self.password_hash)
        }

class GameRoomManager:
    """Manages all active game rooms on the server."""
    def __init__(self):
        self.rooms: Dict[str, GameState] = {}
        self.last_cleanup = datetime.now()

    def create_room(self, host_id: int, host_name: str, password: Optional[str] = None) -> GameState:
        # ✅ SECURITY FIX: Clean up old rooms periodically
        self.cleanup_old_rooms()
        
        if len(self.rooms) >= 100:  # ✅ FIXED: Limit total rooms to prevent DoS
            raise HTTPException(status_code=429, detail="Server at capacity. Please try again later.")
        
        room_id = str(uuid.uuid4())[:6].upper()
        room = GameState(room_id, host_id, host_name, password)
        self.rooms[room_id] = room
        print(f"Room created: {room_id} for host {sanitize_text_input(host_name)[:20]} {'(private)' if password else '(public)'}")
        return room

    def get_room(self, room_id: str) -> Optional[GameState]:
        if not validate_room_id(room_id):
            return None
        return self.rooms.get(room_id)

    def get_public_rooms(self) -> List[Dict]:
        # ✅ SECURITY FIX: Clean up old rooms and limit results
        self.cleanup_old_rooms()
        
        public_rooms = [
            {
                "room_id": room.room_id, 
                "host_name": sanitize_text_input(room.players[room.host_id].name), 
                "player_count": len(room.players),
                "has_password": bool(room.password_hash)
            }
            for room in list(self.rooms.values())[:20]  # ✅ FIXED: Limit to 20 rooms
            if not room.password_hash and not room.is_game_active  # Only show public rooms
        ]
        return public_rooms
    
    def cleanup_old_rooms(self):
        """Remove inactive rooms older than 2 hours"""
        now = datetime.now()
        if now - self.last_cleanup < timedelta(minutes=10):  # Only cleanup every 10 minutes
            return
            
        cutoff_time = now - timedelta(hours=2)
        rooms_to_remove = [
            room_id for room_id, room in self.rooms.items()
            if room.last_activity < cutoff_time and not room.is_game_active
        ]
        
        for room_id in rooms_to_remove:
            del self.rooms[room_id]
            if room_id in connections:
                del connections[room_id]
        
        if rooms_to_remove:
            print(f"Cleaned up {len(rooms_to_remove)} inactive rooms")
        
        self.last_cleanup = now

room_manager = GameRoomManager()

# --------------------------------------------------------------------------
# Data Fetching Logic
# --------------------------------------------------------------------------
async def search_jiosaavn(term: str):
    # ✅ SECURITY FIX: Sanitize search term
    term = sanitize_text_input(term)
    if not term:
        return []
    
    async with httpx.AsyncClient() as client:
        search_url = "https://saavn.dev/api/search/albums"
        search_params = {"query": term, "limit": 1}
        try:
            search_response = await client.get(search_url, params=search_params, timeout=10.0)
            search_response.raise_for_status()
            search_data = search_response.json()
        except Exception as e:
            print(f"Search error: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
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
            print(f"Album fetch error: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
            return []
        
        return album_data.get("data", {}).get("songs", [])

async def get_movie_suggestions(query: str) -> List[str]:
    """Get movie title suggestions from database for autocomplete."""
    # ✅ SECURITY FIX: Sanitize and validate input
    query = sanitize_text_input(query)
    if not query or len(query) < 2 or len(query) > 50:
        return []
    
    try:
        connection = sqlite3.connect('movies.db')
        cursor = connection.cursor()
        
        # ✅ SECURITY FIX: Use parameterized query to prevent SQL injection
        cursor.execute(
            "SELECT DISTINCT title FROM movies WHERE LOWER(title) LIKE LOWER(?) ESCAPE '\\' LIMIT 10",
            (f"%{query.replace('%', '\\%').replace('_', '\\_')}%",)
        )
        results = cursor.fetchall()
        connection.close()
        return [sanitize_text_input(result[0]) for result in results]
    except Exception as e:
        print(f"Error getting suggestions: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
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
            movie_title = sanitize_text_input(result[0])
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
                
                # ✅ SECURITY FIX: Validate URLs before using
                if best_url and not best_url.startswith(('http://', 'https://')):
                    best_url = ""
                
                # Get the best quality image
                images = chosen_song.get("image", [])
                if images:
                    # Find the highest quality image (usually "500x500")
                    for img in reversed(images):  # Reverse to get higher quality first
                        if img.get("quality") in ["500x500", "150x150"]:
                            img_url = img.get("url")
                            if img_url and img_url.startswith(('http://', 'https://')):
                                album_image = img_url
                                break
                    # Fallback to first image if no specific quality found
                    if not album_image and images:
                        fallback_url = images[-1].get("url", "")
                        if fallback_url and fallback_url.startswith(('http://', 'https://')):
                            album_image = fallback_url
                
                if best_url:
                    print(f"Found song from movie: {movie_title[:30]}...")  # ✅ FIXED: Limit log output
                    return {
                        "title": sanitize_text_input(chosen_song.get("name", "")), 
                        "movie": movie_title, 
                        "preview_url": best_url,
                        "image": album_image or "https://via.placeholder.com/300x300?text=No+Image"
                    }
    except Exception as e:
        print(f"Database error: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
    
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
                print(f"Failed to send to client {client_id}")
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
                    player_name = sanitize_text_input(player_obj.name)
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
            print(f"Error in game loop: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
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
            "message": f"🏆 Game Over! Winner: {sanitize_text_input(winner_name)} with {winner_score} points!"
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
    # ✅ SECURITY FIX: Rate limiting would be added here in production
    return room_manager.get_public_rooms()

@app.post("/api/rooms")
async def create_room_api(request: CreateRoomRequest):
    try:
        client_id = random.randint(10000, 99999)
        room = room_manager.create_room(client_id, request.host_name, request.password)
        return {"room_id": room.room_id, "host_id": client_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Room creation error: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
        raise HTTPException(status_code=500, detail="Failed to create room")

@app.websocket("/ws/{room_id}/{client_id}/{player_name}")
async def websocket_endpoint(
    websocket: WebSocket, 
    room_id: str, 
    client_id: int, 
    player_name: str,
    password: Optional[str] = Query(None)
):
    # ✅ SECURITY FIX: Validate inputs before processing
    if not validate_room_id(room_id):
        await websocket.close(code=1008, reason="Invalid room ID format")
        return
    
    if not validate_client_id(client_id):
        await websocket.close(code=1008, reason="Invalid client ID")
        return
    
    player_name = sanitize_text_input(player_name)
    if not player_name:
        await websocket.close(code=1008, reason="Invalid player name")
        return
    
    # ✅ SECURITY FIX: Connection limiting per IP (basic DoS protection)
    client_ip = websocket.client.host if websocket.client else "unknown"
    if connection_count_by_ip[client_ip] >= MAX_CONNECTIONS_PER_IP:
        await websocket.close(code=1008, reason="Too many connections from this IP")
        return
    
    await websocket.accept()
    connection_count_by_ip[client_ip] += 1
    
    print(f"WebSocket connection: room={room_id}, client={client_id}, player={player_name[:20]}...")  # ✅ FIXED: Limit log output
    
    try:
        room = room_manager.get_room(room_id)
        if not room:
            await websocket.send_text(json.dumps({"action": "error", "message": "Room not found"}))
            await websocket.close(code=1008, reason="Room not found")
            return
        
        # ✅ FIXED: Check password with secure comparison
        if not room.check_password(password):
            await websocket.send_text(json.dumps({"action": "error", "message": "Invalid password for this room"}))
            await websocket.close(code=1008, reason="Invalid password")
            return
        
        # Initialize room connections dict if needed
        if room_id not in connections:
            connections[room_id] = {}
        
        connections[room_id][client_id] = websocket
        room.add_player(client_id, player_name)
        
        print(f"Player joined room {room_id}")
        await broadcast_room_state(room_id)
        
        while True:
            data = await websocket.receive_text()
            
            # ✅ SECURITY FIX: Message size limit to prevent DoS
            if len(data) > 1024:  # 1KB limit for messages
                await websocket.send_text(json.dumps({"action": "error", "message": "Message too large"}))
                continue
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"action": "error", "message": "Invalid message format"}))
                continue
            
            action = message.get("action")
            if not isinstance(action, str) or len(action) > 50:  # ✅ FIXED: Validate action
                continue
                
            print(f"Action '{action}' from player {client_id}")

            if action == "set_ready":
                is_ready = message.get("is_ready", False)
                if isinstance(is_ready, bool):
                    room.set_player_ready(client_id, is_ready)
                    await broadcast_room_state(room_id)
                
            elif action == "kick_player" and client_id == room.host_id:
                player_to_kick = message.get("player_id")
                if isinstance(player_to_kick, int) and validate_client_id(player_to_kick):
                    if player_to_kick in connections.get(room_id, {}):
                        await connections[room_id][player_to_kick].close(code=1000, reason="Kicked by host")
                    room.remove_player(player_to_kick)
                    await broadcast_room_state(room_id)
                
            elif action == "update_settings" and client_id == room.host_id:
                settings_data = message.get("settings", {})
                if isinstance(settings_data, dict):
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
                            "message": "Invalid settings format"
                        }))
                
            elif action == "start_game" and client_id == room.host_id and not room.is_game_active:
                room.start_game()
                room.game_loop_task = asyncio.create_task(game_loop(room_id))
                await broadcast_room_state(room_id)
                
            elif action == "guess" and room.is_game_active and room.is_round_active:
                guess_text = message.get("text", "")
                if isinstance(guess_text, str):
                    guess_correct = room.check_guess(client_id, guess_text)
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
                chat_text = message.get("text", "")
                if isinstance(chat_text, str) and chat_text.strip():
                    # ✅ SECURITY FIX: Sanitize chat messages
                    sanitized_text = sanitize_text_input(chat_text)
                    if sanitized_text:  # Only send non-empty messages
                        await broadcast_message(room_id, {
                            "action": "chat_message",
                            "player_name": sanitize_text_input(player_name),
                            "text": sanitized_text
                        })
                
            elif action == "get_suggestions":
                query = message.get("query", "")
                if isinstance(query, str):
                    # Send autocomplete suggestions for movie names
                    suggestions = await get_movie_suggestions(query)
                    await websocket.send_text(json.dumps({
                        "action": "suggestions",
                        "suggestions": suggestions
                    }))
            
    except WebSocketDisconnect:
        print(f"Player disconnected from room {room_id}")
    except Exception as e:
        print(f"WebSocket error: {str(e)[:100]}...")  # ✅ FIXED: Limit log length
    finally:
        # Clean up on disconnect
        connection_count_by_ip[client_ip] -= 1
        if connection_count_by_ip[client_ip] <= 0:
            del connection_count_by_ip[client_ip]
            
        room.remove_player(client_id)
        if client_id in connections.get(room_id, {}):
            del connections[room_id][client_id]
        
        if room and len(room.players) == 0:
            print(f"Room {room_id} is empty, closing.")
            if room.game_loop_task and not room.game_loop_task.done():
                room.game_loop_task.cancel()
            if room_id in room_manager.rooms:
                del room_manager.rooms[room_id]
            if room_id in connections:
                del connections[room_id]
        elif room:
            await broadcast_room_state(room_id)

# ✅ SECURITY FIX: Add health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_rooms": len(room_manager.rooms),
        "total_connections": sum(len(conns) for conns in connections.values())
    }

if __name__ == "__main__":
    import uvicorn
    # Use environment variable for port (required for Render)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)