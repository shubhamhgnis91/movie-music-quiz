"""
WebSocket Routes Module
Handles real-time WebSocket connections for game rooms.
"""

import json
import asyncio
from typing import Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from collections import defaultdict

from app.models.game_state import GameRoomManager, GameState
from app.models.requests import GameSettings
from app.services.validation import (
    validate_room_id, 
    validate_client_id, 
    sanitize_text_input
)
from app.services.game_logic import (
    broadcast_message,
    broadcast_room_state,
    game_loop
)
from app.database.db_manager import get_movie_suggestions

# Create router instance
router = APIRouter()

# WebSocket connections: {room_id: {client_id: WebSocket}}
connections: Dict[str, Dict[int, WebSocket]] = {}

# Connection limiting per IP (DoS protection)
connection_count_by_ip = defaultdict(int)
MAX_CONNECTIONS_PER_IP = 5

# Global room manager instance (will be set by main.py)
room_manager: Optional[GameRoomManager] = None


def set_room_manager(manager: GameRoomManager):
    """Set the global room manager instance."""
    global room_manager
    room_manager = manager


@router.websocket("/ws/{room_id}/{client_id}/{player_name}")
async def websocket_endpoint(
    websocket: WebSocket, 
    room_id: str, 
    client_id: int, 
    player_name: str,
    password: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for game room communication.
    
    Handles:
    - Player join/leave
    - Ready status
    - Game start
    - Guesses
    - Chat messages
    - Settings updates
    - Kick player
    - Movie suggestions
    
    Args:
        websocket: WebSocket connection
        room_id: Room identifier
        client_id: Unique client ID
        player_name: Player's display name
        password: Optional room password
    """
    if not room_manager:
        await websocket.close(code=1011, reason="Server not ready")
        return
    
    # ✅ SECURITY: Validate inputs before processing
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
    
    # ✅ SECURITY: Connection limiting per IP (basic DoS protection)
    client_ip = websocket.client.host if websocket.client else "unknown"
    if connection_count_by_ip[client_ip] >= MAX_CONNECTIONS_PER_IP:
        await websocket.close(code=1008, reason="Too many connections from this IP")
        return
    
    await websocket.accept()
    connection_count_by_ip[client_ip] += 1
    
    print(f"WebSocket connection: room={room_id}, client={client_id}, player={player_name[:20]}...")
    
    try:
        room = room_manager.get_room(room_id)
        if not room:
            await websocket.send_text(json.dumps({"action": "error", "message": "Room not found"}))
            await websocket.close(code=1008, reason="Room not found")
            return
        
        # ✅ SECURITY: Check password with secure comparison
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
        await broadcast_room_state(room_id, connections, room_manager)
        
        while True:
            data = await websocket.receive_text()
            
            # ✅ SECURITY: Message size limit to prevent DoS
            if len(data) > 1024:  # 1KB limit for messages
                await websocket.send_text(json.dumps({"action": "error", "message": "Message too large"}))
                continue
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"action": "error", "message": "Invalid message format"}))
                continue
            
            action = message.get("action")
            if not isinstance(action, str) or len(action) > 50:  # ✅ SECURITY: Validate action
                continue
                
            print(f"Action '{action}' from player {client_id}")

            # Handle different WebSocket actions
            await handle_websocket_action(
                action, message, websocket, room_id, client_id, player_name, room, connections
            )
            
    except WebSocketDisconnect:
        print(f"Player disconnected from room {room_id}")
    except Exception as e:
        print(f"WebSocket error: {str(e)[:100]}...")
    finally:
        # Clean up on disconnect
        await cleanup_connection(room_id, client_id, client_ip, room)


async def handle_websocket_action(
    action: str,
    message: dict,
    websocket: WebSocket,
    room_id: str,
    client_id: int,
    player_name: str,
    room: GameState,
    connections: Dict[str, Dict[int, WebSocket]]
):
    """
    Handle different WebSocket actions.
    
    Args:
        action: Action type string
        message: Full message dict
        websocket: WebSocket connection
        room_id: Room identifier
        client_id: Client ID
        player_name: Player's name
        room: GameState instance
        connections: Global connections dict
    """
    if action == "set_ready":
        is_ready = message.get("is_ready", False)
        if isinstance(is_ready, bool):
            room.set_player_ready(client_id, is_ready)
            await broadcast_room_state(room_id, connections, room_manager)
        
    elif action == "kick_player" and client_id == room.host_id:
        player_to_kick = message.get("player_id")
        if isinstance(player_to_kick, int) and validate_client_id(player_to_kick):
            if player_to_kick in connections.get(room_id, {}):
                await connections[room_id][player_to_kick].close(code=1000, reason="Kicked by host")
            room.remove_player(player_to_kick)
            await broadcast_room_state(room_id, connections, room_manager)
        
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
                    }, connections)
                    await broadcast_room_state(room_id, connections, room_manager)
                else:
                    await websocket.send_text(json.dumps({
                        "action": "error",
                        "message": "Cannot change settings during game"
                    }))
            except Exception:
                await websocket.send_text(json.dumps({
                    "action": "error",
                    "message": "Invalid settings format"
                }))
        
    elif action == "start_game" and client_id == room.host_id and not room.is_game_active:
        room.start_game()
        room.game_loop_task = asyncio.create_task(game_loop(room_id, connections, room_manager))
        await broadcast_room_state(room_id, connections, room_manager)
        
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
                
                await broadcast_room_state(room_id, connections, room_manager)
            
    elif action == "chat":
        chat_text = message.get("text", "")
        if isinstance(chat_text, str) and chat_text.strip():
            # ✅ SECURITY: Sanitize chat messages
            sanitized_text = sanitize_text_input(chat_text)
            if sanitized_text:  # Only send non-empty messages
                await broadcast_message(room_id, {
                    "action": "chat_message",
                    "player_name": sanitize_text_input(player_name),
                    "text": sanitized_text
                }, connections)
        
    elif action == "get_suggestions":
        query = message.get("query", "")
        if isinstance(query, str):
            # Send autocomplete suggestions for movie names
            suggestions = await get_movie_suggestions(query)
            await websocket.send_text(json.dumps({
                "action": "suggestions",
                "suggestions": suggestions
            }))


async def cleanup_connection(
    room_id: str, 
    client_id: int, 
    client_ip: str,
    room: Optional[GameState]
):
    """
    Clean up connection when player disconnects.
    
    Args:
        room_id: Room identifier
        client_id: Client ID
        client_ip: Client IP address
        room: GameState instance or None
    """
    # Decrement IP connection count
    connection_count_by_ip[client_ip] -= 1
    if connection_count_by_ip[client_ip] <= 0:
        del connection_count_by_ip[client_ip]
    
    if room:
        room.remove_player(client_id)
    
    if client_id in connections.get(room_id, {}):
        del connections[room_id][client_id]
    
    if room and len(room.players) == 0:
        print(f"Room {room_id} is empty, closing.")
        if room.game_loop_task and not room.game_loop_task.done():
            room.game_loop_task.cancel()
        if room_manager and room_id in room_manager.rooms:
            del room_manager.rooms[room_id]
        if room_id in connections:
            del connections[room_id]
    elif room:
        await broadcast_room_state(room_id, connections, room_manager)
