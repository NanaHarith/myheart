# speech_service.py
import os
import logging
from datetime import datetime
import webrtcvad
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
log_filename = os.path.join('logs', f"speech_service_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    filename=log_filename,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpeechService:
    def __init__(self):
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(3)  # Aggressive mode for VAD
        self.sample_rate = 16000
        self.frame_duration = 30  # ms
        logger.info("Speech service initialized")
        print("Speech service initialized")

    def process_audio(self, audio_data):
        try:
            logger.info(f"Processing audio data of size: {len(audio_data)}")
            print(f"Processing audio data of size: {len(audio_data)}")

            # VAD requires specific frame sizes: 10, 20, or 30ms at 16kHz
            # For 30ms at 16kHz: 16000 * 0.03 = 480 samples
            frame_size = 480  # 30ms frame at 16kHz

            # Ensure we have enough data for at least one frame
            if len(audio_data) < frame_size:
                logger.warning("Audio buffer too small for processing")
                return None

            # Process frame
            try:
                frame = audio_data[:frame_size]
                is_speech = self.vad.is_speech(frame, self.sample_rate)
                logger.info(f"VAD detection result: {is_speech}")

                if is_speech:
                    return self.transcribe_audio(audio_data)
                return None

            except Exception as e:
                logger.error(f"VAD processing error: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            return None

    # speech_service.py
    # speech_service.py
    def transcribe_audio(self, audio_data):
        try:
            logger.info(f"Transcribing audio chunk of size: {len(audio_data)}")
            print(f"Transcribing audio chunk of size: {len(audio_data)}")

            # For testing, return actual text to verify pipeline
            return "Test transcription"

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            print(f"Error transcribing audio: {str(e)}")
            return None

# Singleton instance
speech_service = SpeechService()