"""
API Routes Module
Handles REST API endpoints for room management and health checks.
"""

from typing import Optional
import random
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.requests import CreateRoomRequest
from app.models.game_state import GameRoomManager

# Create router instance
router = APIRouter()

# Global room manager instance (will be set by main.py)
room_manager: Optional[GameRoomManager] = None


def set_room_manager(manager: GameRoomManager):
    """Set the global room manager instance."""
    global room_manager
    room_manager = manager


@router.get("/")
async def get_homepage():
    """Serve the main application HTML page."""
    return FileResponse("static/index.html")


@router.get("/api/rooms")
async def list_public_rooms():
    """
    Get list of all public (non-password protected) rooms.
    Returns room details including host name and player count.
    """
    if not room_manager:
        raise HTTPException(status_code=500, detail="Room manager not initialized")
    
    return room_manager.get_public_rooms()


@router.post("/api/rooms")
async def create_room_api(request: CreateRoomRequest):
    """
    Create a new game room.
    
    Args:
        request: CreateRoomRequest with host_name and optional password
        
    Returns:
        Dict with room_id and host_id
        
    Raises:
        HTTPException: If room creation fails or server is at capacity
    """
    if not room_manager:
        raise HTTPException(status_code=500, detail="Room manager not initialized")
    
    try:
        client_id = random.randint(10000, 99999)
        room = room_manager.create_room(client_id, request.host_name, request.password)
        return {"room_id": room.room_id, "host_id": client_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Room creation error: {str(e)[:100]}...")
        raise HTTPException(status_code=500, detail="Failed to create room")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns server status and statistics.
    """
    if not room_manager:
        return {
            "status": "initializing",
            "active_rooms": 0,
            "total_connections": 0
        }
    
    # Calculate total connections by accessing websocket module
    try:
        from app.routes import websocket
        total_connections = sum(len(conns) for conns in websocket.connections.values())
    except:
        total_connections = 0
    
    return {
        "status": "healthy",
        "active_rooms": len(room_manager.rooms),
        "total_connections": total_connections
    }
