/**
 * Game Logic Module
 * Handles game state, audio, countdown timer, and guess logic
 */

import { appState } from './state.js';
import { showNotification } from './utils.js';
import { hideSuggestions, closeSettingsModal } from './ui.js';

/**
 * Start the countdown timer
 * @param {number} duration - Duration in seconds
 */
export function startCountdownTimer(duration) {
    stopCountdownTimer();
    
    let timeLeft = duration;
    appState.dom.countdownTimer.textContent = timeLeft;
    appState.dom.countdownTimer.classList.remove('hidden', 'warning', 'critical');
    
    appState.countdownInterval = setInterval(() => {
        timeLeft--;
        appState.dom.countdownTimer.textContent = timeLeft;
        
        // Change styling based on time left
        if (timeLeft <= 5) {
            appState.dom.countdownTimer.classList.add('critical');
            appState.dom.countdownTimer.classList.remove('warning');
        } else if (timeLeft <= 10) {
            appState.dom.countdownTimer.classList.add('warning');
            appState.dom.countdownTimer.classList.remove('critical');
        } else {
            appState.dom.countdownTimer.classList.remove('warning', 'critical');
        }
        
        if (timeLeft <= 0) {
            stopCountdownTimer();
        }
    }, 1000);
}

/**
 * Stop the countdown timer
 */
export function stopCountdownTimer() {
    if (appState.countdownInterval) {
        clearInterval(appState.countdownInterval);
        appState.countdownInterval = null;
    }
    appState.dom.countdownTimer.classList.add('hidden');
    appState.dom.countdownTimer.classList.remove('warning', 'critical');
}

/**
 * Play audio manually (called when autoplay is blocked)
 */
export function playAudioManually() {
    if (appState.dom.audioPlayer.src) {
        appState.dom.audioPlayer.currentTime = 0;
        appState.dom.audioPlayer.play().then(() => {
            appState.dom.manualPlaySection.classList.add('hidden');
            showNotification('Audio playing! 🎵', 'success');
        }).catch(e => {
            console.error('Manual play failed:', e);
            showNotification('Failed to play audio. Please try again.', 'error');
        });
    }
}

/**
 * Load and play audio
 * @param {string} audioUrl - URL of the audio to play
 * @returns {Promise<string>}
 */
export function loadAndPlayAudio(audioUrl) {
    return new Promise((resolve, reject) => {
        if (!audioUrl) {
            reject('No audio URL provided');
            return;
        }

        appState.audioLoadedForRound = false;
        
        const onCanPlay = () => {
            appState.audioLoadedForRound = true;
            appState.dom.audioPlayer.removeEventListener('canplay', onCanPlay);
            appState.dom.audioPlayer.removeEventListener('error', onError);
            
            appState.dom.audioPlayer.currentTime = 0;
            appState.dom.audioPlayer.play().then(() => {
                appState.dom.manualPlaySection.classList.add('hidden');
                resolve('Audio playing');
            }).catch(e => {
                console.log('Autoplay prevented, showing manual play button:', e);
                appState.dom.manualPlaySection.classList.remove('hidden');
                resolve('Manual play required');
            });
        };
        
        const onError = (e) => {
            console.error('Audio loading error:', e);
            appState.dom.audioPlayer.removeEventListener('canplay', onCanPlay);
            appState.dom.audioPlayer.removeEventListener('error', onError);
            reject('Audio loading failed');
        };
        
        appState.dom.audioPlayer.addEventListener('canplay', onCanPlay);
        appState.dom.audioPlayer.addEventListener('error', onError);
        
        appState.dom.audioPlayer.src = audioUrl;
        appState.dom.audioPlayer.load();
    });
}

/**
 * Show audio player (lobby state)
 */
export function showAudioPlayer() {
    appState.dom.audioPlayerSection.classList.remove('hidden');
    appState.dom.mysteryBox.classList.add('hidden');
    appState.dom.manualPlaySection.classList.add('hidden');
    appState.dom.albumReveal.classList.add('hidden');
    appState.dom.songInfo.classList.add('hidden');
    stopCountdownTimer();
}

/**
 * Show mystery box (during round)
 */
export function showMysteryBox() {
    appState.dom.audioPlayerSection.classList.add('hidden');
    appState.dom.mysteryBox.classList.remove('hidden');
    appState.dom.albumReveal.classList.add('hidden');
    appState.dom.songInfo.classList.add('hidden');
    appState.dom.countdownTimer.classList.remove('hidden');
    startCountdownTimer(appState.gameSettings.music_duration);
}

/**
 * Show album reveal (after round)
 * @param {string} albumImageUrl - URL of the album image
 * @param {string} songTitleText - Song title
 * @param {string} movieName - Movie name
 */
export function showAlbumReveal(albumImageUrl, songTitleText, movieName) {
    appState.dom.audioPlayerSection.classList.add('hidden');
    appState.dom.mysteryBox.classList.add('hidden');
    appState.dom.manualPlaySection.classList.add('hidden');
    stopCountdownTimer();
    
    if (albumImageUrl) {
        appState.dom.albumImage.src = albumImageUrl;
        appState.dom.albumReveal.classList.remove('hidden');
    }
    
    if (songTitleText || movieName) {
        if (songTitleText) {
            appState.dom.songTitle.textContent = songTitleText;
        }
        if (movieName) {
            appState.dom.movieTitle.textContent = `From "${movieName}"`;
        }
        appState.dom.songInfo.classList.remove('hidden');
    }
}

/**
 * Handle guess input (typing and enter key)
 * @param {KeyboardEvent} event - Keyboard event
 */
export function handleGuessInput(event) {
    if (!appState.currentRoundActive) {
        appState.dom.guessStatus.textContent = 'Wait for the next round to start!';
        appState.dom.guessStatus.style.color = 'var(--warning-color)';
        return;
    }
    
    clearTimeout(appState.typingTimer);
    const query = event.target.value.trim();
    appState.latestGuess = query;
    
    if (appState.hasSubmittedGuess) {
        appState.dom.guessStatus.textContent = '✓ Guess submitted!';
        appState.dom.guessStatus.style.color = 'var(--success-color)';
        return;
    }
    
    if (query) {
        appState.dom.guessStatus.textContent = 'Type your guess...';
        appState.dom.guessStatus.style.color = 'var(--primary-color)';
    } else {
        appState.dom.guessStatus.textContent = '';
    }
    
    if (query.length >= 2) {
        appState.typingTimer = setTimeout(() => {
            requestSuggestions(query);
        }, 300);
    } else {
        hideSuggestions();
    }
    
    if (event.key === 'Enter' && query && !appState.hasSubmittedGuess) {
        submitGuess();
    }
}

/**
 * Submit a guess to the server
 */
export function submitGuess() {
    const guess = appState.latestGuess || appState.dom.guessInput.value.trim();
    if (!guess || appState.hasSubmittedGuess || !appState.currentRoundActive) return;
    
    if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
        appState.ws.send(JSON.stringify({ action: 'guess', text: guess }));
    }
    
    appState.hasSubmittedGuess = true;
    appState.dom.guessInput.disabled = true;
    appState.dom.guessStatus.textContent = '✓ Guess submitted!';
    appState.dom.guessStatus.style.color = 'var(--success-color)';
    
    hideSuggestions();
}

/**
 * Auto-submit guess when time is running out
 */
export function autoSubmitGuess() {
    if (appState.currentRoundActive && !appState.hasSubmittedGuess && appState.latestGuess) {
        submitGuess();
    }
}

/**
 * Request movie suggestions from server
 * @param {string} query - Search query
 */
export function requestSuggestions(query) {
    if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
        appState.ws.send(JSON.stringify({ action: 'get_suggestions', query: query }));
    }
}

/**
 * Send a WebSocket message to the server
 * @param {object} message - Message object
 */
export function sendMessage(message) {
    if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
        appState.ws.send(JSON.stringify(message));
    } else {
        showNotification('Connection lost. Please rejoin the room.', 'error');
    }
}

/**
 * Set player ready status
 * @param {boolean} isReady - Ready status
 */
export function setReady(isReady) {
    sendMessage({ action: 'set_ready', is_ready: isReady });
}

/**
 * Start the game (host only)
 */
export function startGame() {
    sendMessage({ action: 'start_game' });
    showNotification('Starting the game! 🎮', 'success');
}

/**
 * Kick a player (host only)
 * @param {number} playerId - Player ID to kick
 */
export function kickPlayer(playerId) {
    if (confirm('Are you sure you want to kick this player?')) {
        sendMessage({ action: 'kick_player', player_id: playerId });
    }
}

/**
 * Send a chat message
 */
export function sendChatMessage() {
    const msg = appState.dom.chatInput.value.trim();
    if (msg) {
        sendMessage({ action: 'chat', text: msg });
        appState.dom.chatInput.value = '';
    }
}

/**
 * Save game settings
 */
export function saveSettings() {
    const totalRounds = parseInt(appState.dom.totalRoundsInput.value);
    const musicDuration = parseInt(appState.dom.musicDurationInput.value);
    const gameType = document.querySelector('.game-type-option.selected').dataset.type;
    
    if (totalRounds < 5 || totalRounds > 20) {
        showNotification('Rounds must be between 5 and 20', 'error');
        return;
    }
    
    if (musicDuration < 15 || musicDuration > 60) {
        showNotification('Music duration must be between 15 and 60 seconds', 'error');
        return;
    }
    
    const newSettings = {
        total_rounds: totalRounds,
        music_duration: musicDuration,
        game_type: gameType
    };
    
    sendMessage({
        action: 'update_settings',
        settings: newSettings
    });
    
    appState.gameSettings = newSettings;
    
    closeSettingsModal();
    showNotification('Settings saved successfully!', 'success');
}
