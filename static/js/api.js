/**
 * API Module
 * Handles HTTP requests to the backend API
 */

import { escapeHtml, showNotification } from './utils.js';

/**
 * Load public rooms from the server
 * @returns {Promise<void>}
 */
export async function loadPublicRooms() {
    const publicRoomsList = document.getElementById('publicRoomsList');
    publicRoomsList.innerHTML = '<div class="loading"></div>Loading available rooms...';
    
    try {
        const response = await fetch('/api/rooms');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const rooms = await response.json();
        publicRoomsList.innerHTML = '';
        
        if (rooms.length === 0) {
            publicRoomsList.innerHTML = `
                <div class="room-card" style="text-align: center; color: var(--text-light);">
                    <i class="fas fa-inbox" style="font-size: 2rem; margin-bottom: 10px;"></i>
                    <h3>No public rooms available</h3>
                    <p>Create your own room or join by Room ID!</p>
                </div>
            `;
        } else {
            rooms.forEach(room => {
                const roomEl = document.createElement('div');
                roomEl.className = 'room-card';
                roomEl.innerHTML = `
                    <div class="room-info">
                        <div>
                            <h3><i class="fas fa-users"></i> ${escapeHtml(room.host_name)}'s Room</h3>
                            <p style="color: var(--text-light); margin: 0;">Room ID: ${escapeHtml(room.room_id)}</p>
                        </div>
                        <div style="text-align: right;">
                            <div class="player-count">
                                ${room.player_count} ${room.player_count === 1 ? 'player' : 'players'}
                            </div>
                            <button class="btn btn-outline" onclick="window.gameApp.joinRoom('${escapeHtml(room.room_id)}')" style="margin-top: 10px;">
                                <i class="fas fa-sign-in-alt"></i>
                                Join
                            </button>
                        </div>
                    </div>
                `;
                publicRoomsList.appendChild(roomEl);
            });
        }
    } catch (error) {
        console.error("Failed to load rooms:", error);
        publicRoomsList.innerHTML = `
            <div class="room-card" style="text-align: center; color: var(--danger-color);">
                <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 10px;"></i>
                <h3>Error loading rooms</h3>
                <p>Please check if the server is running correctly.</p>
                <button class="btn btn-outline" onclick="window.gameApp.loadPublicRooms()" style="margin-top: 10px;">
                    <i class="fas fa-sync-alt"></i>
                    Retry
                </button>
            </div>
        `;
        showNotification('Failed to load rooms', 'error');
    }
}

/**
 * Create a new room on the server
 * @param {string} playerName - Host player name
 * @param {string|null} password - Optional room password
 * @returns {Promise<{room_id: string, host_id: number}>}
 */
export async function createRoomAPI(playerName, password = null) {
    const response = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            host_name: playerName, 
            password: password 
        })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}
