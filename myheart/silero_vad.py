import torch
import numpy as np
import sys
import os

# Add the cloned silero-vad repository to the Python path
repo_path = os.path.join(os.path.dirname(__file__), 'silero-vad')
sys.path.append(repo_path)

# Import the necessary utilities from the locally cloned repo
from silero_vad_utils import get_speech_timestamps, read_audio, VADIterator, collect_chunks

class SileroVAD:
    def __init__(self, threshold=0.5):
        # Load the Silero VAD model
        self.model, utils = torch.hub.load(repo_or_dir=repo_path, model='silero_vad', force_reload=True)
        # Unpack the utility functions
        self.get_speech_timestamps, _, self.read_audio, _ = utils
        self.threshold = threshold

    def is_speech(self, audio_data, sample_rate=16000):
        """
        Detect speech in audio data

        Args:
            audio_data (np.ndarray): Audio data as numpy array
            sample_rate (int): Audio sample rate

        Returns:
            bool: Whether speech is detected
        """
        if isinstance(audio_data, np.ndarray):
            audio_tensor = torch.from_numpy(audio_data).float()
        else:
            raise ValueError("Audio data must be a numpy array.")

        # Normalize and ensure single channel
        audio_tensor = audio_tensor / torch.max(torch.abs(audio_tensor))
        if len(audio_tensor.shape) > 1:
            audio_tensor = audio_tensor.mean(dim=1)

        # Get speech timestamps
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=sample_rate
        )
        return len(speech_timestamps) > 0
import torch
import numpy as np
import sys
import os

# Add the cloned silero-vad repository to the Python path
repo_path = os.path.join(os.path.dirname(__file__), 'silero-vad')
sys.path.append(repo_path)

# Import the necessary utilities from the locally cloned repo
from silero_vad import get_speech_timestamps, read_audio, VADIterator, collect_chunks

class SileroVAD:
    def __init__(self, threshold=0.5):
        # Load the Silero VAD model
        self.model, utils = torch.hub.load(repo_or_dir=repo_path, model='silero_vad', force_reload=True)
        # Unpack the utility functions
        self.get_speech_timestamps, _, self.read_audio, _ = utils
        self.threshold = threshold

    def is_speech(self, audio_data, sample_rate=16000):
        """
        Detect speech in audio data

        Args:
            audio_data (np.ndarray): Audio data as numpy array
            sample_rate (int): Audio sample rate

        Returns:
            bool: Whether speech is detected
        """
        if isinstance(audio_data, np.ndarray):
            audio_tensor = torch.from_numpy(audio_data).float()
        else:
            raise ValueError("Audio data must be a numpy array.")

        # Normalize and ensure single channel
        audio_tensor = audio_tensor / torch.max(torch.abs(audio_tensor))
        if len(audio_tensor.shape) > 1:
            audio_tensor = audio_tensor.mean(dim=1)

        # Get speech timestamps
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=sample_rate
        )
        return len(speech_timestamps) > 0
