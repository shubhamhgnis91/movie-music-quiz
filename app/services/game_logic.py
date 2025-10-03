"""
Game Logic Module
Handles the core game loop, round management, and WebSocket broadcasting.
"""

import json
import asyncio
import time
from typing import Dict, TYPE_CHECKING

from app.services.music_service import get_quiz_song
from app.services.validation import sanitize_text_input

if TYPE_CHECKING:
    from fastapi import WebSocket
    from app.models.game_state import GameRoomManager


async def broadcast_message(room_id: str, message: dict, connections: Dict[str, Dict[int, 'WebSocket']]):
    """
    Broadcast a message to all players in a room.
    
    Args:
        room_id: The room to broadcast to
        message: The message dict to send
        connections: Global connections dict
    """
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


async def broadcast_room_state(
    room_id: str, 
    connections: Dict[str, Dict[int, 'WebSocket']], 
    room_manager: 'GameRoomManager'
):
    """
    Broadcast the current room state to all players.
    
    Args:
        room_id: The room to broadcast state for
        connections: Global connections dict
        room_manager: GameRoomManager instance
    """
    room = room_manager.get_room(room_id)
    if room:
        await broadcast_message(room_id, {"action": "update_state", "state": room.get_full_state()}, connections)


async def game_loop(
    room_id: str, 
    connections: Dict[str, Dict[int, 'WebSocket']], 
    room_manager: 'GameRoomManager'
):
    """
    Main game loop that manages rounds, music playback, and scoring.
    
    Args:
        room_id: The room to run the game loop for
        connections: Global connections dict
        room_manager: GameRoomManager instance
    """
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
            }, connections)
            
            # Send round start signal
            await broadcast_message(room_id, {
                "action": "round_start"
            }, connections)
            
            await broadcast_room_state(room_id, connections, room_manager)
            
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
            }, connections)
            
            await broadcast_room_state(room_id, connections, room_manager)  # This will now include the album image
            
            # Send game notification for round end
            correct_answer = room.current_song.get("movie", "Unknown")
            await broadcast_message(room_id, {
                "action": "game_notification",
                "type": "round_end",
                "message": f"⏰ Time's up! The correct answer was: {correct_answer}"
            }, connections)
            
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
                }, connections)
            
            # Send wrong guesses notification  
            if wrong_guessers:
                await broadcast_message(room_id, {
                    "action": "game_notification",
                    "type": "wrong_guesses",
                    "message": f"❌ Wrong: {', '.join(wrong_guessers)}"
                }, connections)
            
            if not correct_guessers and not wrong_guessers:
                await broadcast_message(room_id, {
                    "action": "game_notification",
                    "type": "no_guesses",
                    "message": "🤷 Nobody made a guess this round!"
                }, connections)
            
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
        }, connections)
    
    await broadcast_message(room_id, {"action": "game_over", "leaderboard": room.scores}, connections)
    print(f"Game in room {room_id} has ended.")
