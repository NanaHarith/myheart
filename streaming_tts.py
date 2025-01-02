# streaming_tts.py

import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Available emotions: angry, cheerful, sad, terrified, relaxed, fearful, surprised, calm, assertive, energetic, warm, direct, bright
SPEECHIFY_EMOTION = "cheerful"
SPEECHIFY_EMOTION_INTENSITY = 1.5  # Range: 0.0 to 2.0
SPEECHIFY_SPEED = 1.3  # Default speed (1.0 is normal speed)
SPEECHIFY_PITCH = 1.2  # Default pitch (1.0 is normal pitch)

# Load environment variables
load_dotenv()

# Configure logging
from logging_config import setup_logging
logger = setup_logging('streaming_tts')

class StreamingTTS:
    def __init__(self):
        self.sp_api_key = os.getenv('SP_API_KEY')
        self.voice_id = "28c4d41d-8811-4ca0-9515-377d6ca2c715"  # or "henry" for built-in voice
        self.base_url = "https://api.sws.speechify.com/v1"
        print(f"\nSpeechify Initialization:")
        print(f"API Key present: {'Yes' if self.sp_api_key else 'No'}")

    def wrap_text_with_emotion(self, text):
        return f'<speak><speechify:style emotion="{SPEECHIFY_EMOTION}">{text}</speechify:style></speak>'

    def get_stream(self, text):
        try:
            headers = {
                "Authorization": f"Bearer {self.sp_api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
            payload = {
                "input": self.wrap_text_with_emotion(text),
                "voice_id": self.voice_id,
                "output_format": "mp3",
                "emotion_intensity": SPEECHIFY_EMOTION_INTENSITY,
                "speed": SPEECHIFY_SPEED,
                "pitch": SPEECHIFY_PITCH
            }
            print("\nSpeechify Stream Request:")
            print(f"Text: {text[:100]}...")
            print(f"URL: {self.base_url}/audio/stream")
            print(f"Headers: {headers}")
            print(f"Payload: {payload}")
            response = requests.post(
                f"{self.base_url}/audio/stream",
                headers=headers,
                json=payload,
                stream=True
            )
            print(f"Response Status: {response.status_code}")
            if response.status_code == 200:
                audio_data = b''.join(response.iter_content(chunk_size=1024))
                print(f"Stream Success: Received {len(audio_data)} bytes")
                logger.info(f"Received audio stream of size: {len(audio_data)} bytes")
                return audio_data
            else:
                print(f"Stream Error: {response.status_code}")
                print(f"Error Response: {response.text}")
                logger.error(f"Stream error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Stream Exception: {str(e)}")
            logger.error(f"Stream exception: {str(e)}")
            return None

    def get_speech(self, text):
        try:
            headers = {
                "Authorization": f"Bearer {self.sp_api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
            payload = {
                "input": self.wrap_text_with_emotion(text),
                "voice_id": self.voice_id,
                "output_format": "mp3",
                "emotion_intensity": SPEECHIFY_EMOTION_INTENSITY,
                "speed": SPEECHIFY_SPEED,
                "pitch": SPEECHIFY_PITCH
            }
            print("\nSpeechify Speech Request:")
            print(f"Text: {text[:100]}...")
            print(f"URL: {self.base_url}/audio/speech")
            print(f"Headers: {headers}")
            print(f"Payload: {payload}")
            response = requests.post(
                f"{self.base_url}/audio/speech",
                headers=headers,
                json=payload
            )
            print(f"Response Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Speech Success: Received {len(response.content)} bytes")
                logger.info(f"Received audio speech of size: {len(response.content)} bytes")
                return response.content
            else:
                print(f"Speech Error: {response.status_code}")
                print(f"Error Response: {response.text}")
                logger.error(f"Speech error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Speech Exception: {str(e)}")
            logger.error(f"Speech exception: {str(e)}")
            return None

# Singleton instance
tts_service = StreamingTTS()
