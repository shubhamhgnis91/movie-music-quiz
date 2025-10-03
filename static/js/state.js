/**
 * Application State Module
 * Manages global application state
 */

export const appState = {
    // WebSocket connection
    ws: null,
    
    // Player information
    clientId: null,
    playerName: null,
    roomId: null,
    isHost: false,
    currentRoomPassword: null,
    
    // Game state
    currentRoundActive: false,
    hasSubmittedGuess: false,
    latestGuess: '',
    audioLoadedForRound: false,
    
    // Timers
    typingTimer: null,
    countdownInterval: null,
    
    // Game settings
    gameSettings: {
        total_rounds: 10,
        music_duration: 30,
        game_type: 'regular'
    },
    
    // DOM Elements (initialized on load)
    dom: {}
};

/**
 * Initialize DOM element references
 */
export function initializeDOM() {
    appState.dom = {
        // Views
        views: document.querySelectorAll('.view'),
        
        // Home view elements
        playerNameInput: document.getElementById('playerNameInput'),
        passwordInput: document.getElementById('passwordInput'),
        roomIdInput: document.getElementById('roomIdInput'),
        joinPasswordInput: document.getElementById('joinPasswordInput'),
        publicRoomsList: document.getElementById('publicRoomsList'),
        
        // Room view elements
        roomIdSpan: document.getElementById('roomIdSpan'),
        playerList: document.getElementById('playerList'),
        scoreBoard: document.getElementById('scoreBoard'),
        roundInfo: document.getElementById('roundInfo'),
        currentRoundSpan: document.getElementById('currentRound'),
        totalRoundsSpan: document.getElementById('totalRounds'),
        
        // Game display elements
        audioPlayerSection: document.getElementById('audioPlayerSection'),
        audioPlayer: document.getElementById('audioPlayer'),
        mysteryBox: document.getElementById('mysteryBox'),
        manualPlaySection: document.getElementById('manualPlaySection'),
        albumReveal: document.getElementById('albumReveal'),
        albumImage: document.getElementById('albumImage'),
        songInfo: document.getElementById('songInfo'),
        songTitle: document.getElementById('songTitle'),
        movieTitle: document.getElementById('movieTitle'),
        countdownTimer: document.getElementById('countdownTimer'),
        
        // Guess elements
        guessInput: document.getElementById('guessInput'),
        guessStatus: document.getElementById('guessStatus'),
        suggestionsDiv: document.getElementById('suggestions-list'),
        
        // Chat elements
        chatBox: document.getElementById('chatBox'),
        chatInput: document.getElementById('chatInput'),
        notificationsList: document.getElementById('notificationsList'),
        
        // Settings modal
        settingsModal: document.getElementById('settingsModal'),
        totalRoundsInput: document.getElementById('totalRoundsInput'),
        musicDurationInput: document.getElementById('musicDurationInput')
    };
}

/**
 * Reset game state (called when leaving room)
 */
export function resetGameState() {
    appState.currentRoundActive = false;
    appState.hasSubmittedGuess = false;
    appState.latestGuess = '';
    appState.audioLoadedForRound = false;
    appState.isHost = false;
    appState.currentRoomPassword = null;
    
    if (appState.typingTimer) {
        clearTimeout(appState.typingTimer);
        appState.typingTimer = null;
    }
    
    if (appState.countdownInterval) {
        clearInterval(appState.countdownInterval);
        appState.countdownInterval = null;
    }
}
