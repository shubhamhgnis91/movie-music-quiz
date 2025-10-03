"""
Movie Music Quiz - Main Application Entry Point

A real-time multiplayer music quiz game where players guess Bollywood movie names
from song snippets. Built with FastAPI and WebSockets.

Security features:
- Input sanitization and validation
- Rate limiting
- Secure password hashing
- Security headers (CSP, HSTS, etc.)
- Connection limiting per IP

Author: GitHub Copilot & User
License: MIT
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.middleware.security import SecurityHeadersMiddleware
from app.models.game_state import GameRoomManager
from app.database.db_manager import initialize_database
from app.routes import api, websocket

# Initialize FastAPI application
app = FastAPI(
    title="Movie Music Quiz",
    description="Real-time multiplayer Bollywood music quiz game",
    version="2.0.0"
)

# Mount static files (CSS, JS, images)
app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/js", StaticFiles(directory="static/js"), name="js")

# --------------------------------------------------------------------------
# Middleware Configuration
# --------------------------------------------------------------------------

# Security headers middleware (must be first)
app.add_middleware(SecurityHeadersMiddleware)

# Trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.TRUSTED_HOSTS
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Session middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# --------------------------------------------------------------------------
# Application Startup
# --------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialize database and global state on application startup."""
    print("🚀 Starting Movie Music Quiz Server...")
    print(f"📊 Environment: {'Production' if settings.ENVIRONMENT == 'production' else 'Development'}")
    
    # Initialize database
    initialize_database()
    
    # Create global room manager instance
    room_manager = GameRoomManager()
    
    # Set room manager in route modules
    api.set_room_manager(room_manager)
    websocket.set_room_manager(room_manager)
    
    print("✅ Server initialized successfully!")
    print(f"🎵 Ready to host music quiz games!")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    print("👋 Shutting down Movie Music Quiz Server...")
    
    # Cancel all active game loops
    if hasattr(api, 'room_manager') and api.room_manager:
        for room in api.room_manager.rooms.values():
            if room.game_loop_task and not room.game_loop_task.done():
                room.game_loop_task.cancel()
    
    print("✅ Shutdown complete!")

# --------------------------------------------------------------------------
# Route Registration
# --------------------------------------------------------------------------

# Include API routes (REST endpoints)
app.include_router(api.router, tags=["API"])

# Include WebSocket routes
app.include_router(websocket.router, tags=["WebSocket"])

# --------------------------------------------------------------------------
# Application Entry Point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # Get port from environment variable (required for Render deployment)
    port = int(os.environ.get("PORT", 8000))
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
