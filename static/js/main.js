let pc, dc, mediaStream;
let tokenRefreshInterval;
let audioEl;
let fullTranscript = '';
let currentAudioPlayback = null;
let reconnectAttempts = 0;
let currentSessionId = null;
let currentConversationId = null;
const MAX_RECONNECT_ATTEMPTS = 5;
let conversationHistory = [];

function logAPIResponse(message) {
    try {
        if (message.rate_limits) {
            console.log('Rate Limits:', {
                remaining: message.rate_limits.remaining,
                reset: message.rate_limits.reset,
                limit: message.rate_limits.limit
            });
        }
        if (message.type === 'error') {
            console.error('API Error:', message.error);
            updateStatus(`Error: ${message.error.message || 'Unknown error'}`);
        }
        switch (message.type) {
            case 'rate_limits.updated':
                console.log('Rate limits updated:', message);
                break;
            case 'session.created':
                currentSessionId = message.session.id;
                console.log('Session created:', currentSessionId);
                break;
            case 'session.updated':
                console.log('Session updated:', message);
                break;
        }
    } catch (error) {
        console.error('Error logging API response:', error);
    }
}

// Modified token refresh to maintain session
async function getEphemeralToken() {
    console.log('Requesting ephemeral token...');
    try {
        const response = await fetch('/get_ephemeral_token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                conversation_id: currentConversationId,
                conversation_history: conversationHistory
            })
        });
        const data = await response.json();
        console.log('Ephemeral token received successfully');
        return data.client_secret.value;
    } catch (error) {
        console.error('Error getting ephemeral token:', error);
        throw error;
    }
}

async function refreshToken() {
    try {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('Max reconnection attempts reached');
            stopTokenRefresh();
            updateStatus('Connection expired. Please restart manually.');
            return;
        }
        reconnectAttempts++;
        const newToken = await getEphemeralToken();
        await reconnectWithNewToken(newToken);
        console.log('Token refreshed successfully');
        reconnectAttempts = 0;
    } catch (error) {
        console.error('Token refresh failed:', error);
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000);
        setTimeout(refreshToken, delay);
    }
}

function startTokenRefresh(expirationTime = 60000) {
    const refreshTime = Math.max(expirationTime - 15000, 30000);
    if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval);
    }
    tokenRefreshInterval = setInterval(refreshToken, refreshTime);
    console.log(`Token refresh scheduler started with interval: ${refreshTime}ms`);
}

function stopTokenRefresh() {
    if (tokenRefreshInterval) {
        clearInterval(tokenRefreshInterval);
        console.log('Token refresh scheduler stopped');
    }
}

async function reconnectWithNewToken(newToken) {
    if (pc) {
        pc.close();
    }
    await initWebRTC(newToken);
}

function updateStatus(message) {
    const statusBox = document.getElementById('status');
    if (statusBox) {
        console.log('Status update:', message);
        statusBox.textContent = message;
    } else {
        console.error('Status box element not found');
    }
}

// Add conversation history tracking
function handleServerMessage(event) {
    try {
        const message = JSON.parse(event.data);
        console.log('Message received:', JSON.stringify(message, null, 2));
        
        // Track session and conversation IDs
        if (message.type === 'session.created') {
            currentSessionId = message.session.id;
            console.log('Session created:', currentSessionId);
        }
        if (message.type === 'conversation.created') {
            currentConversationId = message.conversation.id;
            console.log('Conversation created:', currentConversationId);
        }
        
        // Store conversation items
        if (message.type === 'conversation.item.created') {
            if (message.item) {
                conversationHistory.push({
                    id: message.item.id,
                    role: message.item.role,
                    content: message.item.content,
                    previous_item_id: message.previous_item_id
                });
            }
        }
        switch (message.type) {
            case 'conversation.created':
                currentConversationId = message.conversation.id;
                console.log('Conversation created:', currentConversationId);
                break;
            case 'input_audio_buffer.speech_started':
                console.log('Speech detected');
                updateStatus('Speech detected - listening...');
                if (currentAudioPlayback) {
                    currentAudioPlayback.pause();
                    currentAudioPlayback = null;
                }
                break;
            case 'conversation.item.input_audio_transcription.completed':
                console.log('Transcription completed:', message.transcript);
                const userTranscript = message.transcript?.trim();
                const transcriptionBox = document.querySelector('#transcription');
                if (transcriptionBox && userTranscript) {
                    console.log('Updating transcription box');
                    const formattedText = userTranscript.replace(/\n/g, '<br>');
                    if (transcriptionBox.innerHTML === 'Transcribed audio will appear here...') {
                        transcriptionBox.innerHTML = `You: ${formattedText}`;
                    } else {
                        transcriptionBox.innerHTML += `<br><br>You: ${formattedText}`;
                    }
                } else {
                    console.error('Transcription box not found or empty transcript');
                }
                break;
            
            case 'response.audio_transcript.delta':
            case 'response.audio_transcript.done':
            case 'response.content_part.added':
                const responseBox = document.querySelector('#response');
                if (responseBox) {
                    const newText = message.delta?.text || message.transcript || message.content?.text;
                    if (newText?.trim()) {
                        if (responseBox.innerHTML === 'AI response will appear here...') {
                            responseBox.innerHTML = '';
                        }
                        const formattedResponse = newText.replace(/\n/g, '<br>');
                        if (!responseBox.innerHTML.includes(formattedResponse)) {
                            if (responseBox.innerHTML === '') {
                                responseBox.innerHTML = `Your Dear: ${formattedResponse}`;
                            } else {
                                responseBox.innerHTML += `<br><br>Your Dear: ${formattedResponse}`;
                            }
                            sendTextToSpeechify(newText);
                        }
                    }
                }
                break;
            case 'input_audio_buffer.speech_stopped':
                updateStatus('Processing speech...');
                break;
            case 'error':
                console.error('API Error:', message.error);
                updateStatus(`Error: ${message.error.message || 'Unknown error'}`);
                break;
            default:
                console.log(`Received ${message.type} message:`, message);
        }
        
        if (message.rate_limits) {
            console.log('Rate Limits:', message.rate_limits);
        }
    } catch (error) {
        console.error('Error processing message:', error);
        console.error('Raw message data:', event.data);
    }
}

function sendMessage(message) {
    if (dc && dc.readyState === 'open') {
        console.log('Sending message:', message.type);
        dc.send(JSON.stringify(message));
    } else {
        console.error('Cannot send message, channel not open. Current state:', dc?.readyState);
    }
}

async function sendTextToSpeechify(text) {
    try {
        if (currentAudioPlayback) {
            currentAudioPlayback.pause();
            currentAudioPlayback = null;
        }

        const response = await fetch('/get_speech', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text }),
        });

        if (response.ok) {
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            currentAudioPlayback = audio;
            audio.play();
        } else {
            console.error('Failed to get speech from Speechify');
        }
    } catch (error) {
        console.error('Error sending text to Speechify:', error);
    }
}

async function initWebRTC(token = null) {
    console.log('Initializing WebRTC connection...');
    try {
        const transcriptionBox = document.querySelector('#transcription');
        const responseBox = document.querySelector('#response');
        if (transcriptionBox) {
            transcriptionBox.innerHTML = 'Transcribed audio will appear here...';
        }
        if (responseBox) {
            responseBox.innerHTML = 'AI response will appear here...';
        }

        const EPHEMERAL_KEY = token || await getEphemeralToken();
        pc = new RTCPeerConnection();
        console.log('RTCPeerConnection created');
        audioEl = new Audio();
        audioEl.autoplay = true;
        
        pc.ontrack = (event) => {
            console.log('Received audio track');
            const [track] = event.streams[0].getAudioTracks();
            if (track) {
                const stream = new MediaStream([track]);
                // Commenting out OpenAI audio playback
                // audioEl.srcObject = stream;
                // audioEl.play().catch(e => console.error('Audio playback error:', e));
            }
        };

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log('Audio permission granted');
        mediaStream.getTracks().forEach(track => pc.addTrack(track, mediaStream));

        dc = pc.createDataChannel("oai-events");
        console.log('Data channel created');
        dc.onopen = () => {
            console.log('Data channel is now open');
            sendMessage({
                type: "session.update",
                session: {
                    input_audio_transcription: {
                        model: "whisper-1"
                    }
                }
            });
            sendMessage({
                type: "response.create",
                response: {
                    modalities: ["text", "audio"],
                    instructions: "You are My Dear. Only say Hi.",
                },
            });
            updateStatus('Connected and ready for voice input...');
            console.log('Data channel state:', dc.readyState);
            console.log('RTCPeerConnection state:', pc.connectionState);
        };
        
        dc.onclose = () => console.log('Data channel closed');
        dc.onerror = (error) => console.error('Data channel error:', error);
        dc.onmessage = handleServerMessage;

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        console.log('Local description set');

        const baseUrl = "https://api.openai.com/v1/realtime";
        const model = "gpt-4o-realtime-preview-2024-12-17";
        const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
            method: "POST",
            body: offer.sdp,
            headers: {
                Authorization: `Bearer ${EPHEMERAL_KEY}`,
                "Content-Type": "application/sdp"
            },
        });

        const answer = {
            type: "answer",
            sdp: await sdpResponse.text(),
        };
        await pc.setRemoteDescription(answer);
        console.log('Remote description set, WebRTC connection established');
        updateStatus('Connected and listening...');
        startTokenRefresh();
    } catch (error) {
        console.error('Error in WebRTC initialization:', error);
        updateStatus('Connection failed. Please try again.');
        throw error;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('Application initialized');
    document.getElementById('startButton').addEventListener('click', async () => {
        console.log('Start button clicked');
        updateStatus('Connecting...');
        fullTranscript = '';
        try {
            await initWebRTC();
            document.getElementById('startButton').disabled = true;
            document.getElementById('stopButton').disabled = false;
        } catch (error) {
            console.error('Failed to start session:', error);
            updateStatus('Failed to start. Please try again.');
        }
    });


    document.getElementById('stopButton').addEventListener('click', () => {
        console.log('Stop button clicked');
        stopTokenRefresh();
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
        }
        if (pc) {
            pc.close();
        }
        document.getElementById('startButton').disabled = false;
        document.getElementById('stopButton').disabled = true;
        updateStatus('Ready to listen...');
        console.log('Session ended');
    });
});
