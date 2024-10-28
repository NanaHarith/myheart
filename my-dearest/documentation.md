# Application Overview

## Functionality

The application is a web-based interactive assistant that uses speech recognition and text-to-speech (TTS) capabilities to communicate with users. It listens for user commands, processes them using OpenAI's language model, and responds with synthesized speech.

## Architecture

The application is built using Flask for the backend, with Socket.IO for real-time communication between the server and the client. The client-side is implemented using HTML, CSS, and JavaScript, leveraging the Web Speech API for speech recognition.

### Key Components

1. **Flask Application (`app.py`)**:
   - Manages HTTP routes and WebSocket events.
   - Handles user connections and disconnections.
   - Processes transcriptions and generates AI responses.
   - Manages audio playback and listening states.

2. **Streaming TTS (`streaming_tts.py`)**:
   - Interfaces with the Speechify API to generate audio from text.
   - Streams audio data to the client.

3. **Client-side (`index.html`)**:
   - Provides a user interface for interaction.
   - Uses Web Speech API for speech recognition.
   - Manages audio playback and displays AI responses.

4. **Static Assets**:
   - Includes audio files and stylesheets.

## Features

- **Real-time Speech Recognition**: Uses the Web Speech API to capture and transcribe user speech.
- **AI Response Generation**: Sends user transcriptions to OpenAI's API to generate responses.
- **Text-to-Speech**: Converts AI responses to audio using the Speechify API.
- **Connection Management**: Handles user connections and disconnections gracefully.
- **Audio Playback Control**: Manages audio playback states to prevent overlapping responses.
- **User Interface**: Provides a simple interface for starting and stopping listening sessions.

## Dependencies

- Flask
- Flask-SocketIO
- OpenAI API
- WebRTC VAD
- Speechify API
- Web Speech API (client-side)

## Environment Variables

- `OPENAI_API_KEY`: API key for OpenAI.
- `SP_API_KEY`: API key for Speechify.
