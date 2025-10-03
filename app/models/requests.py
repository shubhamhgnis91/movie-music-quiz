"""
Pydantic request/response models.
Data validation and serialization for API requests.
"""
from typing import Optional
from pydantic import BaseModel, validator
from app.config import settings
from app.services.validation import sanitize_text_input


class CreateRoomRequest(BaseModel):
    """Request model for creating a new game room."""
    host_name: str
    password: Optional[str] = None
    
    @validator('host_name')
    def validate_host_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Host name is required')
        v = sanitize_text_input(v)
        if len(v) > settings.MAX_NAME_LENGTH:
            raise ValueError(f'Host name too long (max {settings.MAX_NAME_LENGTH} characters)')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > settings.MAX_PASSWORD_LENGTH:
                raise ValueError(f'Password too long (max {settings.MAX_PASSWORD_LENGTH} characters)')
        return v


class GameSettings(BaseModel):
    """Game configuration settings."""
    total_rounds: int = 10
    music_duration: int = 30  # seconds
    game_type: str = "regular"  # "regular" or "speed"
    
    @validator('total_rounds')
    def validate_rounds(cls, v):
        if not settings.MIN_ROUNDS <= v <= settings.MAX_ROUNDS:
            raise ValueError(f'Total rounds must be between {settings.MIN_ROUNDS} and {settings.MAX_ROUNDS}')
        return v
    
    @validator('music_duration')
    def validate_duration(cls, v):
        if not settings.MIN_MUSIC_DURATION <= v <= settings.MAX_MUSIC_DURATION:
            raise ValueError(f'Music duration must be between {settings.MIN_MUSIC_DURATION} and {settings.MAX_MUSIC_DURATION} seconds')
        return v
    
    @validator('game_type')
    def validate_game_type(cls, v):
        if v not in ['regular', 'speed']:
            raise ValueError('Game type must be "regular" or "speed"')
        return v


class Player(BaseModel):
    """Player model."""
    id: int
    name: str
    is_ready: bool = False
