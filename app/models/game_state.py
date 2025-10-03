"""
Game state management models.
Manages individual game rooms and the global room manager.
"""
import asyncio
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.config import settings
from app.models.requests import Player, GameSettings
from app.services.validation import sanitize_text_input, validate_room_id


class GameState:
    """Manages the state of a single game room."""
    
    def __init__(self, room_id: str, host_id: int, host_name: str, password: Optional[str] = None):
        self.room_id: str = room_id
        self.host_id: int = host_id
        self.password: Optional[str] = password
        self.password_hash: Optional[str] = None
        
        # Hash passwords instead of storing plaintext
        if password:
            self.password_hash = hashlib.sha256(password.encode()).hexdigest()
            self.password = None  # Don't store plaintext
        
        self.players: Dict[int, Player] = {
            host_id: Player(id=host_id, name=sanitize_text_input(host_name))
        }
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
        """
        Check if the provided password matches the room password.
        
        Args:
            provided_password: Password to verify
            
        Returns:
            True if password matches or no password required
        """
        if not self.password_hash:  # No password required
            return True
        if provided_password is None:  # Password required but none provided
            return False
        
        # Compare hashed passwords using timing-attack resistant comparison
        provided_hash = hashlib.sha256(provided_password.encode()).hexdigest()
        return hmac.compare_digest(self.password_hash, provided_hash)

    def update_settings(self, settings_obj: GameSettings) -> bool:
        """
        Update game settings (only allowed before game starts).
        
        Args:
            settings_obj: New game settings
            
        Returns:
            True if settings were updated
        """
        if not self.is_game_active:
            self.total_rounds = settings_obj.total_rounds
            self.music_duration = settings_obj.music_duration
            self.game_type = settings_obj.game_type
            self.last_activity = datetime.now()
            return True
        return False

    def add_player(self, player_id: int, player_name: str) -> bool:
        """
        Add a player to the room.
        
        Args:
            player_id: Unique player ID
            player_name: Player display name
            
        Returns:
            True if player was added
        """
        if player_id not in self.players and len(self.players) < settings.MAX_PLAYERS_PER_ROOM:
            self.players[player_id] = Player(id=player_id, name=sanitize_text_input(player_name))
            self.last_activity = datetime.now()
            return True
        return False

    def remove_player(self, player_id: int) -> None:
        """Remove a player from the room."""
        if player_id in self.players:
            del self.players[player_id]
        if player_id in self.scores:
            del self.scores[player_id]
        self.last_activity = datetime.now()
    
    def set_player_ready(self, player_id: int, is_ready: bool) -> None:
        """Set a player's ready status."""
        if player_id in self.players:
            self.players[player_id].is_ready = is_ready
            self.last_activity = datetime.now()

    def start_game(self) -> None:
        """Initialize scores for all players and start the game."""
        self.is_game_active = True
        self.current_round = 0
        self.scores = {player_id: 0 for player_id in self.players}
        self.players_who_guessed.clear()
        self.guess_times.clear()
        self.last_activity = datetime.now()

    def start_round(self) -> None:
        """Start a new round."""
        self.is_round_active = True
        self.is_reveal_phase = False
        self.round_start_time = time.time()
        self.players_who_guessed.clear()
        self.guess_times.clear()
        self.last_activity = datetime.now()

    def end_round(self) -> None:
        """End the current round."""
        self.is_round_active = False
        self.last_activity = datetime.now()

    def start_reveal_phase(self) -> None:
        """Start the reveal phase (show album image)."""
        self.is_round_active = False
        self.is_reveal_phase = True
        self.last_activity = datetime.now()

    def check_guess(self, player_id: int, guess_text: str) -> Optional[bool]:
        """
        Check if a player's guess is correct and update score.
        
        Args:
            player_id: ID of guessing player
            guess_text: The guess text
            
        Returns:
            True if correct, False if wrong, None if invalid
        """
        if not self.is_round_active or player_id in self.players_who_guessed:
            return None
        
        if player_id not in self.scores:
            self.scores[player_id] = 0
        
        # Sanitize guess input
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
        """
        Get the complete state of the room for broadcasting.
        
        Returns:
            Dictionary representing room state
        """
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
        """
        Create a new game room.
        
        Args:
            host_id: ID of room host
            host_name: Name of room host
            password: Optional room password
            
        Returns:
            Created GameState instance
            
        Raises:
            ValueError: If max rooms limit reached
        """
        # Clean up old rooms periodically
        self.cleanup_old_rooms()
        
        if len(self.rooms) >= settings.MAX_ROOMS:
            raise ValueError(f"Maximum room limit ({settings.MAX_ROOMS}) reached")
        
        room_id = str(uuid.uuid4())[:6].upper()
        room = GameState(room_id, host_id, host_name, password)
        self.rooms[room_id] = room
        print(f"Room created: {room_id} for host {sanitize_text_input(host_name)[:20]} "
              f"{'(private)' if password else '(public)'}")
        return room

    def get_room(self, room_id: str) -> Optional[GameState]:
        """Get a room by ID."""
        if not validate_room_id(room_id):
            return None
        return self.rooms.get(room_id)

    def get_public_rooms(self) -> List[Dict]:
        """
        Get list of public (non-password protected) rooms.
        
        Returns:
            List of room info dictionaries
        """
        # Clean up old rooms and limit results
        self.cleanup_old_rooms()
        
        public_rooms = [
            {
                "room_id": room.room_id,
                "host_name": sanitize_text_input(room.players[room.host_id].name),
                "player_count": len(room.players),
                "has_password": bool(room.password_hash)
            }
            for room in list(self.rooms.values())[:20]  # Limit to 20 rooms
            if not room.password_hash and not room.is_game_active  # Only public, non-active rooms
        ]
        return public_rooms
    
    def cleanup_old_rooms(self) -> None:
        """Remove inactive rooms older than configured timeout."""
        now = datetime.now()
        if now - self.last_cleanup < timedelta(minutes=settings.ROOM_CLEANUP_INTERVAL_MINUTES):
            return  # Don't cleanup too frequently
            
        cutoff_time = now - timedelta(hours=settings.ROOM_INACTIVE_TIMEOUT_HOURS)
        rooms_to_remove = [
            room_id for room_id, room in self.rooms.items()
            if room.last_activity < cutoff_time and not room.is_game_active
        ]
        
        for room_id in rooms_to_remove:
            print(f"Cleaning up inactive room: {room_id}")
            del self.rooms[room_id]
        
        if rooms_to_remove:
            print(f"Cleaned up {len(rooms_to_remove)} inactive rooms")
        
        self.last_cleanup = now


# Global room manager instance
room_manager = GameRoomManager()
