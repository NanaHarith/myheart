# audio_utils.py
import logging
from datetime import datetime
import numpy as np

# Configure logging
log_filename = f"audio_utils_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1024

    def normalize_audio(self, audio_data):
        try:
            # Convert to numpy array if not already
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Normalize to [-1, 1] range
            normalized = audio_array.astype(np.float32) / 32768.0

            # Ensure audio doesn't clip
            if np.max(np.abs(normalized)) > 1.0:
                normalized = normalized / np.max(np.abs(normalized))

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing audio: {str(e)}")
            return None

    def prepare_audio_data(self, raw_audio):
        try:
            # Convert to mono if needed
            if self.channels == 1:
                audio_data = self.to_mono(raw_audio)
            else:
                audio_data = raw_audio

            # Normalize the audio
            normalized_audio = self.normalize_audio(audio_data)

            return normalized_audio

        except Exception as e:
            logger.error(f"Error preparing audio data: {str(e)}")
            return None

    def to_mono(self, audio_data):
        try:
            # Convert stereo to mono if necessary
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_array.shape) > 1:
                return np.mean(audio_array, axis=1).astype(np.int16)
            return audio_array

        except Exception as e:
            logger.error(f"Error converting to mono: {str(e)}")
            return None


# Singleton instance
audio_processor = AudioProcessor()