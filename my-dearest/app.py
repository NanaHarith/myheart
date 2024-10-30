import os
import io
import threading
from flask import Flask, render_template, send_from_directory, request, send_file, jsonify
from hello import hello
from flask_socketio import SocketIO, emit
from openai import OpenAI
from dotenv import load_dotenv
import webrtcvad
import streaming_tts  # Import the streaming TTS module
import wave
import audio_fingerprint  # Import the audio fingerprinting module
import requests
from pydub import AudioSegment
from gtts import gTTS
import tempfile
from pydub.silence import split_on_silence

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
conversation_history = []
listening_active = False  # Flag to indicate if the system is actively listening
is_playing_audio = False  # Flag to indicate if audio is being played
vad = webrtcvad.Vad(3)  # Aggressiveness mode (0-3)

# Flag to toggle streaming TTS
USE_STREAMING_TTS = True

# Speechify API settings
API_BASE_URL = "https://api.sws.speechify.com"
API_KEY = os.getenv("SP_API_KEY") # Replace with your actual API key
# VOICE_ID = "cc0ff3e9-582a-4bb38db8-d084e10963e0"
VOICE_ID = "28c4d41d-8811-4ca0-9515-377d6ca2c715"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/beep')
def serve_beep():
    return send_from_directory('static/audio', 'beep.mp3', mimetype='audio/mpeg')

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('start_listening')
def start_listening():
    global listening_active
    listening_active = True
    emit('listening_status', {'status': 'started'}, broadcast=True)
    print("Listening started")

@socketio.on('stop_listening')
def stop_listening():
    global listening_active
    listening_active = False
    emit('listening_status', {'status': 'stopped'})
    print("Listening stopped")

last_transcription = None

@socketio.on('transcription')
def handle_transcription(transcription):
    global listening_active, last_transcription

    # Debounce duplicate transcriptions
    if transcription == last_transcription:
        print("Duplicate transcription ignored")
        return
    last_transcription = transcription

    if not listening_active:
        print("Not listening")
        return

    # Check if the transcription matches the last AI response
    if conversation_history and conversation_history[-1]["role"] == "assistant":
        last_response = conversation_history[-1]["content"].strip().lower()
        current_transcription = transcription.strip().lower()
        
        # Use pydub to analyze audio and check for matches
        if is_audio_matching(current_transcription, last_response):
            print("Ignoring transcription that matches the last AI response")
            return

    print(f"Received transcription: {transcription}")
    process_command(transcription)
    socketio.sleep(0.1)  # Add a slight delay to prevent overwhelming the server

def process_command(command):
    conversation_history.append({"role": "user", "content": command})
    response = get_ai_response(conversation_history)
    try:
        try:
            emit('ai_response', {'text': response, 'is_final': True})
            global is_playing_audio
            audio_url = streaming_tts.generate_audio(response)
            is_playing_audio = True  # Set flag to true when starting audio playback
            emit('audio_response', {'url': audio_url}, broadcast=True)
        except (ConnectionAbortedError, ConnectionResetError) as e:
            print(f"Connection issue: {str(e)}")
        except Exception as e:
            print(f"Error during response emission: {str(e)}")
    except (ConnectionAbortedError, BrokenPipeError) as e:
        print(f"Connection issue: {str(e)}")
    except Exception as e:
        print(f"Error during response emission: {str(e)}")
    
    # Immediately re-enable listening after processing
    # Ensure listening is re-enabled after processing
    listening_active = True
    emit('listening_status', {'status': 'started'}, broadcast=True)
def is_audio_matching(transcription, response):
    print(f"Checking if transcription matches response: '{transcription}' vs '{response}'")
    audio = AudioSegment.from_file("static/audio/response.mp3")
    
    # Split audio on silence to get chunks
    chunks = split_on_silence(audio, min_silence_len=500, silence_thresh=-40)
    
    # Convert transcription and response to lowercase
    transcription = transcription.lower()
    response = response.lower()
    
    # Extract features from the response audio
    response_features = audio_fingerprint.extract_features(audio)
    
    # Convert transcription to audio using gTTS
    tts = gTTS(text=transcription, lang='en')
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        temp_filename = fp.name
    tts.save(temp_filename)
    transcription_audio = AudioSegment.from_file(temp_filename, format="mp3")
    os.remove(temp_filename)
    transcription_features = audio_fingerprint.extract_features(transcription_audio)
    
    print(f"Transcription features: {transcription_features}")
    print(f"Response features: {response_features}")
    match = audio_fingerprint.compare_fingerprints(transcription_features, response_features)
    
    print(f"Fingerprint match result: {match}")
    return match

def reset_listening():
    global listening_active
    listening_active = True
    print("Listening re-enabled after cooldown")

@socketio.on('audio_data')
def handle_audio_data(data):
    global is_playing_audio
    if is_playing_audio:
        emit('speech_detected', {'detected': False})
        return
    # Process and emit audio data
    try:
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(data)
            audio_data = wav_io.getvalue()

        audio = wave.open(io.BytesIO(audio_data), 'rb')
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            print("Audio format not supported: must be mono and 16-bit")
            emit('speech_detected', {'detected': False})
            return

        sample_rate = audio.getframerate()
        audio_data = audio.readframes(audio.getnframes())

        frame_duration = 30  # in milliseconds
        frame_size = int(sample_rate * (frame_duration / 1000.0) * 2)
        offset = 0
        speech_detected = False
        while offset + frame_size <= len(audio_data):
            frame = audio_data[offset:offset + frame_size]
            if vad.is_speech(frame, sample_rate):
                speech_detected = True
                break
            offset += frame_size

        emit('speech_detected', {'detected': speech_detected})
    except wave.Error as e:
        print(f"Wave error in handle_audio_data: {str(e)}")
        emit('speech_detected', {'detected': False})
    except Exception as e:
        print(f"Error in handle_audio_data: {str(e)}")
        emit('speech_detected', {'detected': False})

def get_ai_response(conversation):
    print("Sending request to OpenAI")
    conversation.insert(0, {
        "role": "system",
        "content": (
            "You are a calm, soothing assistant who speaks in a warm, empathetic, and gentle manner. "
            "Your responses should make the user feel heard and understood, similar to a therapist. "
            "Always provide thoughtful and reflective answers that help the user feel comforted."
        )
    })
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation,
            stream=True
        )
        final_reply_content = ""
        last_emitted_content = ""
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                final_reply_content += chunk.choices[0].delta.content
                partial_reply_content = final_reply_content.strip()
                if partial_reply_content != last_emitted_content:
                    print(f"Emitting partial response: {partial_reply_content}")
                    emit('ai_response', {'text': partial_reply_content, 'is_final': False})
                    last_emitted_content = partial_reply_content

        final_reply_content = final_reply_content.strip()
        conversation_history.append({"role": "assistant", "content": final_reply_content})
        emit('ai_response', {'text': final_reply_content, 'is_final': True})
        return final_reply_content
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        return "Sorry, there was an error processing your request."


@socketio.on('request_audio')
def handle_request_audio(data):
    try:
        audio_data = streaming_tts.generate_audio(data['text'])
        if audio_data:
            emit('audio_data', audio_data, broadcast=True, binary=True)
        else:
            emit('audio_error', {'error': 'Failed to generate audio'})
    except Exception as e:
        emit('audio_error', {'error': str(e)})

@socketio.on('audio_finished')
def handle_audio_finished():
    global is_playing_audio
    is_playing_audio = False  # Reset the flag when audio playback is finished
    reset_listening()

if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True)
