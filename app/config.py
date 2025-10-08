"""
Application configuration and constants.
Centralized configuration management for environment variables and app settings.
"""
import os
import secrets


class Settings:
    """Application settings and configuration."""
    
    # Security
    SECRET_KEY: str = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.environ.get("PORT", 8000))
    
    # CORS Origins
    CORS_ORIGINS: list[str] = [
        "https://movie-music-quiz.onrender.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://localhost:8000"
    ]
    
    # Trusted Hosts
    TRUSTED_HOSTS: list[str] = [
        "movie-music-quiz.onrender.com",
        "localhost",
        "127.0.0.1",
	"192.168.1.45",
	"shubhamsingh91.in",
	"*.shubhamsingh91.in"
    ]
    
    # Environment
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 60
    MAX_CONNECTIONS_PER_IP: int = 5
    
    # Game Settings
    MAX_ROOMS: int = 100
    MAX_PLAYERS_PER_ROOM: int = 10
    MIN_ROUNDS: int = 5
    MAX_ROUNDS: int = 20
    MIN_MUSIC_DURATION: int = 15
    MAX_MUSIC_DURATION: int = 60
    ROOM_CLEANUP_INTERVAL_MINUTES: int = 10
    ROOM_INACTIVE_TIMEOUT_HOURS: int = 2
    
    # Input Validation
    MAX_TEXT_INPUT_LENGTH: int = 100
    MAX_NAME_LENGTH: int = 50
    MAX_PASSWORD_LENGTH: int = 100
    MAX_MESSAGE_SIZE: int = 1024  # bytes
    MIN_SUGGESTION_QUERY_LENGTH: int = 2
    MAX_SUGGESTION_QUERY_LENGTH: int = 50
    MAX_MOVIE_TITLE_LENGTH: int = 200
    
    # Database
    DB_PATH: str = os.environ.get("DB_PATH", "movies.db")
    
    # External APIs
    JIOSAAVN_SEARCH_URL: str = "https://saavn.dev/api/search/albums"
    JIOSAAVN_ALBUM_URL: str = "https://saavn.dev/api/albums"
    
    # Demo Song (fallback)
    DEMO_SONG: dict = {
        "title": "Demo Song",
        "movie": "Demo Movie",
        "preview_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "image": "https://via.placeholder.com/300x300?text=Demo+Album"
    }
    
    @classmethod
    def check_secret_key_warning(cls) -> None:
        """Warn if using auto-generated SECRET_KEY."""
        if not os.environ.get("SECRET_KEY"):
            print("⚠️  WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY environment variable in production!")


# Create global settings instance
settings = Settings()

# Show warning if needed
settings.check_secret_key_warning()
