import os
import io
from flask import Flask, render_template, send_from_directory, request, send_file, jsonify
from flask_socketio import SocketIO, emit
from openai import OpenAI
from dotenv import load_dotenv
import webrtcvad
import wave
import requests

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
conversation_history = []
listening_active = False  # Flag to indicate if the system is actively listening
is_playing_audio = False  # Flag to indicate if audio is being played
vad = webrtcvad.Vad(3)  # Aggressiveness mode (0-3)

# Speechify API settings
API_BASE_URL = "https://api.sws.speechify.com"
API_KEY = os.getenv("SP_API_KEY") #"moD37t5o_gbknINcGGtHdnp9KiZOzQrmiMakliIcoVk="  # Replace with your actual API key
# VOICE_ID = "cc0ff3e9-582a-4bb3-8db8-d084e10963e0"
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
    print("Listening started")

@socketio.on('stop_listening')
def stop_listening():
    global listening_active
    listening_active = False
    print("Listening stopped")

@socketio.on('transcription')
def handle_transcription(transcription):
    global listening_active

    if not listening_active:
        print("Not listening")
        return

    print(f"Received transcription: {transcription}")
    process_command(transcription)

def process_command(command):
    conversation_history.append({"role": "user", "content": command})
    response = get_ai_response(conversation_history)
    emit('ai_response', {'text': response, 'is_final': True})
    global is_playing_audio
    audio_url = generate_audio(response)
    is_playing_audio = True  # Set flag to true when starting audio playback
    emit('audio_response', {'url': audio_url})

@socketio.on('audio_data')
def handle_audio_data(data):
    global is_playing_audio
    if is_playing_audio:
        emit('speech_detected', {'detected': False})
        return
    if is_speech(data):
        emit('speech_detected', {'detected': True})
    else:
        emit('speech_detected', {'detected': False})

def is_speech(audio_data):
    try:
        audio = wave.open(io.BytesIO(audio_data), 'rb')
        sample_rate = audio.getframerate()
        audio_data = audio.readframes(audio.getnframes())

        frame_duration = 30  # in milliseconds
        frame_size = int(sample_rate * (frame_duration / 1000.0) * 2)
        offset = 0
        while offset + frame_size <= len(audio_data):
            frame = audio_data[offset:offset + frame_size]
            if vad.is_speech(frame, sample_rate):
                return True
            offset += frame_size
        return False
    except Exception as e:
        print(f"Error in is_speech: {str(e)}")
        return False

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

        collected_messages = []
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                collected_messages.append(chunk.choices[0].delta.content)
                full_reply_content = ''.join(collected_messages).strip()
                print(f"Emitting partial response: {full_reply_content}")
                emit('ai_response', {'text': full_reply_content, 'is_final': False})

        full_reply_content = ''.join(collected_messages).strip()
        conversation_history.append({"role": "assistant", "content": full_reply_content})
        return full_reply_content
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        return "Sorry, there was an error processing your request."

def generate_audio(text):
    try:
        response = requests.post(f"{API_BASE_URL}/v1/audio/stream", json={
            "input": f"<speak>{text}</speak>",
            "voice_id": VOICE_ID,
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        })

        if response.ok:
            return f"/stream_audio?text={text}"
        else:
            print(f"Failed to generate audio: {response.status_code}")
            print(f"Response content: {response.content}")  # Add this line for more debug info
            return None

    except Exception as e:
        print(f"Error in generate_audio: {str(e)}")
        return None

@app.route('/stream_audio')
def stream_audio():
    text = request.args.get('text')
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        response = requests.post(f"{API_BASE_URL}/v1/audio/stream", json={
            "input": f"<speak>{text}</speak>",
            "voice_id": VOICE_ID,
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        })

        if response.ok:
            audio_stream = io.BytesIO(response.content)
            response = send_file(audio_stream, mimetype='audio/mpeg')
            is_playing_audio = False  # Reset flag after audio playback
            return response
        else:
            return jsonify({"error": "Failed to stream audio"}), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True)
