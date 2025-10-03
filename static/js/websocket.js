/**
 * WebSocket Module
 * Handles WebSocket connection and message handling
 */

import { appState, resetGameState } from './state.js';
import { showNotification, escapeHtml, getPlayerInitials } from './utils.js';
import { showView, addGameNotification, highlightCorrectPlayer, addChatMessage, showSuggestions } from './ui.js';
import { loadAndPlayAudio, showMysteryBox, showAlbumReveal, showAudioPlayer, autoSubmitGuess, stopCountdownTimer } from './game.js';
import { loadPublicRooms } from './api.js';

/**
 * Connect to WebSocket for a room
 * @param {string} newRoomId - Room ID to join
 * @param {string|null} roomPassword - Optional room password
 */
export function connectWebSocket(newRoomId, roomPassword = null) {
    appState.roomId = newRoomId;
    appState.currentRoomPassword = roomPassword;
    appState.clientId = appState.clientId || Math.floor(Math.random() * 90000) + 10000;

    const encodedPlayerName = encodeURIComponent(appState.playerName);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsUrl = `${protocol}//${window.location.host}/ws/${appState.roomId}/${appState.clientId}/${encodedPlayerName}`;
    
    if (roomPassword) {
        wsUrl += `?password=${encodeURIComponent(roomPassword)}`;
    }

    console.log("Connecting to WebSocket:", wsUrl.replace(/password=[^&]+/, 'password=***'));
    appState.ws = new WebSocket(wsUrl);
    
    appState.ws.onopen = handleWebSocketOpen;
    appState.ws.onmessage = handleWebSocketMessage;
    appState.ws.onclose = handleWebSocketClose;
    appState.ws.onerror = handleWebSocketError;
}

/**
 * Handle WebSocket connection open
 */
function handleWebSocketOpen() {
    console.log("Connected to room " + appState.roomId);
    showView('room-view');
    showAudioPlayer();
    showNotification(`Connected to room ${appState.roomId}`, 'success');
    addGameNotification(`Welcome to room ${appState.roomId}! 🎉`, 'round_start');
    
    // Clear input fields
    appState.dom.roomIdInput.value = '';
    appState.dom.joinPasswordInput.value = '';
    appState.dom.passwordInput.value = '';
}

/**
 * Handle WebSocket messages from server
 * @param {MessageEvent} event - WebSocket message event
 */
function handleWebSocketMessage(event) {
    const message = JSON.parse(event.data);
    console.log("Server message:", message);
    
    switch (message.action) {
        case "update_state":
            renderRoomState(message.state);
            break;
            
        case "chat_message":
            const isOwn = message.player_name === appState.playerName && message.player_name !== 'System';
            addChatMessage(message.player_name, message.text, isOwn);
            break;
            
        case "game_notification":
            addGameNotification(message.message, message.type);
            if (message.type === 'correct_guesses' && message.correct_players) {
                message.correct_players.forEach(playerName => {
                    highlightCorrectPlayer(playerName);
                });
            }
            break;
            
        case "suggestions":
            showSuggestions(message.suggestions);
            break;
            
        case "guess_result":
            if (message.correct) {
                appState.dom.guessStatus.textContent = `✓ Correct! +${message.points_earned} points`;
                appState.dom.guessStatus.style.color = 'var(--success-color)';
            } else {
                appState.dom.guessStatus.textContent = '❌ Wrong answer';
                appState.dom.guessStatus.style.color = 'var(--danger-color)';
            }
            break;
            
        case "round_start":
            handleRoundStart();
            break;
            
        case "round_end":
            handleRoundEnd(message);
            break;
            
        case "game_over":
            handleGameOver();
            break;
            
        case "settings_updated":
            appState.gameSettings = message.settings;
            showNotification('Game settings updated!', 'info');
            break;
            
        case "error":
            showNotification(message.message, 'error');
            showView('home-view');
            break;
    }
}

/**
 * Handle round start
 */
function handleRoundStart() {
    appState.currentRoundActive = true;
    appState.hasSubmittedGuess = false;
    appState.latestGuess = '';
    
    showMysteryBox();
    appState.dom.guessInput.disabled = false;
    appState.dom.guessInput.value = '';
    appState.dom.guessStatus.textContent = 'Listen carefully and type your guess!';
    appState.dom.guessStatus.style.color = 'var(--primary-color)';
    
    // Auto-submit before time runs out
    setTimeout(() => {
        autoSubmitGuess();
    }, (appState.gameSettings.music_duration - 1) * 1000);
}

/**
 * Handle round end
 * @param {object} message - Round end message
 */
function handleRoundEnd(message) {
    appState.currentRoundActive = false;
    appState.dom.audioPlayer.pause();
    appState.dom.manualPlaySection.classList.add('hidden');
    appState.dom.guessInput.disabled = true;
    stopCountdownTimer();
    
    console.log('Round ended, song data:', message);
    if (message.album_image || message.song_title || message.correct_answer) {
        showAlbumReveal(message.album_image, message.song_title, message.correct_answer);
    }
    
    if (!appState.hasSubmittedGuess) {
        appState.dom.guessStatus.textContent = `⏰ Time's up! Answer: ${message.correct_answer}`;
        appState.dom.guessStatus.style.color = 'var(--warning-color)';
    }
}

/**
 * Handle game over
 */
function handleGameOver() {
    appState.currentRoundActive = false;
    appState.dom.audioPlayer.pause();
    appState.dom.manualPlaySection.classList.add('hidden');
    appState.dom.guessInput.disabled = true;
    appState.dom.guessStatus.textContent = 'Game finished!';
    appState.dom.guessStatus.style.color = 'var(--info-color)';
    stopCountdownTimer();
    showAudioPlayer();
}

/**
 * Handle WebSocket connection close
 * @param {CloseEvent} event - WebSocket close event
 */
function handleWebSocketClose(event) {
    console.error("WebSocket closed:", event);
    const reason = event.reason || "Connection lost";
    if (reason === "Invalid password") {
        showNotification('Incorrect password for this room', 'error');
    } else if (reason === "Room not found") {
        showNotification('Room not found', 'error');
    } else {
        showNotification(`Disconnected: ${reason}`, 'error');
    }
    
    appState.dom.audioPlayer.pause();
    stopCountdownTimer();
    resetGameState();
    showView('home-view');
    
    loadPublicRooms();
}

/**
 * Handle WebSocket error
 * @param {Event} error - WebSocket error event
 */
function handleWebSocketError(error) {
    console.error("WebSocket error:", error);
    showNotification('Connection error occurred', 'error');
}

/**
 * Render room state from server update
 * @param {object} state - Room state object
 */
function renderRoomState(state) {
    appState.dom.roomIdSpan.textContent = state.room_id;
    appState.isHost = (appState.clientId === state.host_id);
    
    appState.gameSettings.total_rounds = state.total_rounds;
    appState.gameSettings.music_duration = state.music_duration;
    appState.gameSettings.game_type = state.game_type;
    
    // Update round indicator
    if (state.is_game_active) {
        appState.dom.roundInfo.style.display = 'block';
        appState.dom.currentRoundSpan.textContent = state.current_round;
        appState.dom.totalRoundsSpan.textContent = state.total_rounds;
        
        if (state.is_reveal_phase && state.current_song) {
            console.log('Showing reveal phase with song:', state.current_song);
            showAlbumReveal(
                state.current_song.image, 
                state.current_song.title, 
                state.current_song.movie
            );
        } else if (state.is_round_active) {
            if (!appState.dom.mysteryBox.classList.contains('hidden') === false) {
                showMysteryBox();
            }
        }
    } else {
        appState.dom.roundInfo.style.display = 'none';
        showAudioPlayer();
    }
    
    // Update player list
    renderPlayerList(state);
    
    // Update scoreboard
    renderScoreboard(state);
    
    // Handle audio
    handleAudio(state);
}

/**
 * Render player list
 * @param {object} state - Room state
 */
function renderPlayerList(state) {
    appState.dom.playerList.innerHTML = '';
    state.players.forEach((p) => {
        const isHostPlayer = p.id === state.host_id;
        const isMe = p.id === appState.clientId;
        
        const playerEl = document.createElement('div');
        playerEl.className = 'player-item';
        
        const statusClass = p.is_ready ? 'status-ready' : 'status-not-ready';
        const statusText = p.is_ready ? 'Ready' : 'Not Ready';
        const statusIcon = p.is_ready ? 'check-circle' : 'clock';
        
        let actions = '';
        if (appState.isHost && !isMe && !state.is_game_active) {
            actions += `<button class="btn btn-danger" onclick="window.gameApp.kickPlayer(${p.id})" style="padding: 6px 10px; font-size: 0.8rem;"><i class="fas fa-user-times"></i></button>`;
        }
        if (isMe && !appState.isHost && !state.is_game_active) {
            const readyAction = p.is_ready ? 'Unready' : 'Ready';
            const readyIcon = p.is_ready ? 'times' : 'check';
            actions += `<button class="btn btn-outline" onclick="window.gameApp.setReady(${!p.is_ready})" style="padding: 6px 10px; font-size: 0.8rem;"><i class="fas fa-${readyIcon}"></i> ${readyAction}</button>`;
        }
        if (isMe && appState.isHost && !state.is_game_active) {
            actions += `<button class="btn btn-outline" onclick="window.gameApp.showSettingsModal()" style="padding: 6px 10px; font-size: 0.8rem; margin-right: 5px;"><i class="fas fa-cog"></i></button>`;
            actions += `<button class="btn btn-success" onclick="window.gameApp.startGame()" style="padding: 6px 12px; font-size: 0.8rem;"><i class="fas fa-play"></i> Start</button>`;
        }
        
        playerEl.innerHTML = `
            <div class="player-info">
                <div class="player-avatar">${escapeHtml(getPlayerInitials(p.name))}</div>
                <div>
                    <div style="font-weight: 600; font-size: 0.9rem;">
                        ${escapeHtml(p.name)} 
                        ${isHostPlayer ? '<i class="fas fa-crown" style="color: #ffd700; margin-left: 5px;"></i>' : ''}
                        ${isMe ? '<span style="color: var(--primary-color); font-size: 0.7rem; margin-left: 5px;">(You)</span>' : ''}
                    </div>
                    <div class="${statusClass}" style="font-size: 0.8rem;">
                        <i class="fas fa-${statusIcon}"></i> ${statusText}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 5px;">
                ${actions}
            </div>
        `;
        
        appState.dom.playerList.appendChild(playerEl);
    });
}

/**
 * Render scoreboard
 * @param {object} state - Room state
 */
function renderScoreboard(state) {
    appState.dom.scoreBoard.innerHTML = '';
    
    if (Object.keys(state.scores).length === 0) {
        let gameTypeDesc = state.game_type === 'speed' ? 
            'Speed mode: Faster guesses = more points!' : 
            'Regular mode: 10 points per correct answer';
            
        appState.dom.scoreBoard.innerHTML = `
            <div style="text-align: center; color: var(--text-light); padding: 20px;">
                <i class="fas fa-trophy" style="font-size: 2rem; margin-bottom: 10px;"></i>
                <p style="margin-bottom: 10px;">Scores will appear here once the game starts!</p>
                <p style="font-size: 0.85rem;">${gameTypeDesc}</p>
            </div>
        `;
    } else {
        const sortedScores = Object.entries(state.scores).sort((a, b) => b[1] - a[1]);
        sortedScores.forEach(([pid, score], index) => {
            const playerObj = state.players.find(p => p.id == pid);
            const pName = playerObj?.name || 'Unknown';
            
            const scoreEl = document.createElement('div');
            let rankClass = '';
            let rankIcon = '';
            
            if (index === 0) {
                rankClass = 'first';
                rankIcon = '<i class="fas fa-crown" style="color: #ffd700; margin-right: 8px;"></i>';
            } else if (index === 1) {
                rankClass = 'second';
                rankIcon = '<i class="fas fa-medal" style="color: #c0c0c0; margin-right: 8px;"></i>';
            } else if (index === 2) {
                rankClass = 'third';
                rankIcon = '<i class="fas fa-medal" style="color: #cd7f32; margin-right: 8px;"></i>';
            } else {
                rankIcon = `<span style="margin-right: 8px; font-weight: bold; font-size: 0.9rem;">${index + 1}.</span>`;
            }
            
            scoreEl.className = `score-item ${rankClass}`;
            scoreEl.innerHTML = `
                <div style="display: flex; align-items: center;">
                    ${rankIcon}
                    <div class="player-avatar" style="width: 28px; height: 28px; font-size: 0.7rem; margin-right: 8px;">
                        ${escapeHtml(getPlayerInitials(pName))}
                    </div>
                    <span class="player-name" style="font-weight: 500; font-size: 0.9rem;">${escapeHtml(pName)}</span>
                </div>
                <div style="font-weight: 600; font-size: 1rem; color: var(--primary-color);">
                    ${score}
                </div>
            `;
            
            appState.dom.scoreBoard.appendChild(scoreEl);
        });
    }
}

/**
 * Handle audio loading and playback
 * @param {object} state - Room state
 */
function handleAudio(state) {
    if (state.current_song && state.current_song.preview_url && state.is_round_active) {
        if (appState.dom.audioPlayer.src !== state.current_song.preview_url) {
            console.log('Loading new audio:', state.current_song.preview_url);
            loadAndPlayAudio(state.current_song.preview_url).then((result) => {
                console.log('Audio load result:', result);
            }).catch((error) => {
                console.error('Audio load failed:', error);
                showNotification('Failed to load audio. Please check your connection.', 'error');
            });
        }
    } else if (state.current_song && state.current_song.preview_url) {
        if (appState.dom.audioPlayer.src !== state.current_song.preview_url) {
            appState.dom.audioPlayer.src = state.current_song.preview_url;
        }
    }
}
