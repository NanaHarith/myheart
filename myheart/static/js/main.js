document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const statusDiv = document.getElementById('status');
    const transcriptDiv = document.getElementById('transcript');
    const responseDiv = document.getElementById('response');
    let recognition;
    let isListening = false;
    let socket;
    let currentAudio = null;

    function updateStatus(message) {
        statusDiv.textContent = message;
    }

    function initSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window)) {
            updateStatus('Speech recognition not supported');
            return null;
        }

        recognition = new webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            updateStatus('Listening...');
            startBtn.textContent = 'Stop Listening';
        };

        recognition.onresult = (event) => {
            const result = event.results[event.results.length - 1];
            const transcript = result[0].transcript;

            // Always update the transcript display
            transcriptDiv.textContent = transcript;

            if (result.isFinal) {
                updateStatus('Processing speech...');
                if (transcript.trim().length > 0) {
                    socket.emit('user_transcript', { text: transcript });
                }
            } else {
                updateStatus('Waiting for you to finish...');
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            updateStatus(`Error: ${event.error}`);
        };

        recognition.onend = () => {
            if (isListening) {
                recognition.start();
            } else {
                updateStatus('Ready');
                startBtn.textContent = 'Start Listening';
            }
        };

        return recognition;
    }

    function connectSocket() {
        socket = io();

        socket.on('connect', () => {
            console.log('Socket.IO connected');
            updateStatus('Connected');
        });

        socket.on('disconnect', () => {
            console.log('Socket.IO disconnected');
            updateStatus('Disconnected');
        });

        socket.on('response', (data) => {
            updateStatus('Generating response...');
            if (data.text) {
                responseDiv.textContent = data.text;
            }
            if (data.audio) {
                // Stop listening while audio plays
                if (recognition && isListening) {
                    stopListening();
                }

                if (currentAudio) {
                    currentAudio.pause();
                    URL.revokeObjectURL(currentAudio.src);
                }

                updateStatus('Speaking...');
                const audioBlob = new Blob([data.audio], { type: 'audio/mpeg' });
                const audioUrl = URL.createObjectURL(audioBlob);
                currentAudio = new Audio(audioUrl);

                currentAudio.onended = () => {
                    updateStatus('Ready');
                    if (!isListening) {
                        startListening();
                    }
                };

                currentAudio.play();
            }
        });
    }

    function startListening() {
        if (!recognition) {
            recognition = initSpeechRecognition();
        }
        if (recognition) {
            isListening = true;
            recognition.start();
        }
    }

    function stopListening() {
        if (recognition) {
            isListening = false;
            recognition.stop();
        }
    }

    startBtn.addEventListener('click', () => {
        if (!isListening) {
            startListening();
        } else {
            stopListening();
        }
    });

    // Initial Socket.IO connection
    connectSocket();
});