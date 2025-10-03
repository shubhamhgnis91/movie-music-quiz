/**
 * Main Application Module
 * Entry point that initializes and coordinates all modules
 */

import { appState, initializeDOM, resetGameState } from './state.js';
import { showNotification } from './utils.js';
import { loadPublicRooms, createRoomAPI } from './api.js';
import { showView, showSettingsModal, closeSettingsModal, hideSuggestions } from './ui.js';
import { 
    handleGuessInput, 
    sendChatMessage, 
    setReady, 
    startGame, 
    kickPlayer, 
    saveSettings,
    playAudioManually,
    stopCountdownTimer 
} from './game.js';
import { connectWebSocket } from './websocket.js';

/**
 * Initialize the application
 */
function init() {
    // Initialize DOM references
    initializeDOM();
    
    // Show home view
    showView('home-view');
    
    // Load public rooms
    loadPublicRooms();
    
    // Focus on player name input
    appState.dom.playerNameInput.focus();
    
    // Set up event listeners
    setupEventListeners();
    
    // Auto-refresh rooms every 10 seconds
    setInterval(() => {
        if (document.getElementById('home-view').classList.contains('active')) {
            loadPublicRooms();
        }
    }, 10000);
    
    console.log('Movie Music Quiz initialized!');
}

/**
 * Set up global event listeners
 */
function setupEventListeners() {
    // Click outside to hide suggestions
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#guessInput') && !e.target.closest('#suggestions-list')) {
            hideSuggestions();
        }
    });
    
    // Room ID input auto-uppercase
    if (appState.dom.roomIdInput) {
        appState.dom.roomIdInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase();
        });
    }
    
    // Escape key to close modals and suggestions
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideSuggestions();
            closeSettingsModal();
        }
    });
    
    // Game type selection in settings modal
    document.querySelectorAll('.game-type-option').forEach(option => {
        option.addEventListener('click', () => {
            document.querySelectorAll('.game-type-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            option.classList.add('selected');
        });
    });
    
    // Chat input enter key
    appState.dom.chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });
    
    // Guess input handler
    appState.dom.guessInput.addEventListener('keyup', handleGuessInput);
}

/**
 * Create a new room
 */
async function createRoom() {
    if (!appState.dom.playerNameInput.value.trim()) {
        showNotification('Please enter your name', 'error');
        appState.dom.playerNameInput.focus();
        return;
    }
    
    appState.playerName = appState.dom.playerNameInput.value.trim();
    appState.currentRoomPassword = appState.dom.passwordInput.value.trim() || null;
    
    try {
        const data = await createRoomAPI(appState.playerName, appState.currentRoomPassword);
        appState.clientId = data.host_id;
        appState.isHost = true;
        joinRoom(data.room_id, appState.currentRoomPassword);
        showNotification('Room created successfully!', 'success');
    } catch (error) {
        console.error("Failed to create room:", error);
        showNotification('Could not create room. Please try again.', 'error');
    }
}

/**
 * Join a room by ID (from input)
 */
function joinRoomById() {
    const roomIdToJoin = appState.dom.roomIdInput.value.trim().toUpperCase();
    const password = appState.dom.joinPasswordInput.value.trim() || null;
    
    if (!roomIdToJoin) {
        showNotification('Please enter a Room ID', 'error');
        appState.dom.roomIdInput.focus();
        return;
    }
    
    if (!appState.dom.playerNameInput.value.trim()) {
        showNotification('Please enter your name first', 'error');
        appState.dom.playerNameInput.focus();
        return;
    }
    
    joinRoom(roomIdToJoin, password);
}

/**
 * Join a room (establishes WebSocket connection)
 * @param {string} newRoomId - Room ID to join
 * @param {string|null} roomPassword - Optional room password
 */
function joinRoom(newRoomId, roomPassword = null) {
    if (!appState.dom.playerNameInput.value.trim() && !appState.playerName) {
        showNotification('Please enter your name', 'error');
        appState.dom.playerNameInput.focus();
        return;
    }
    
    appState.playerName = appState.dom.playerNameInput.value.trim() || appState.playerName;
    connectWebSocket(newRoomId, roomPassword);
}

/**
 * Leave the current room
 */
function leaveRoom() {
    if (appState.ws) {
        appState.ws.close();
    }
    appState.dom.audioPlayer.pause();
    stopCountdownTimer();
    resetGameState();
    showView('home-view');
    loadPublicRooms();
    showNotification('Left the room', 'info');
}

/**
 * Expose public API for global window access
 * (Required for onclick handlers in HTML)
 */
window.gameApp = {
    createRoom,
    joinRoom,
    joinRoomById,
    leaveRoom,
    loadPublicRooms,
    setReady,
    startGame,
    kickPlayer,
    sendChatMessage,
    showSettingsModal,
    closeSettingsModal,
    saveSettings,
    playAudioManually
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
