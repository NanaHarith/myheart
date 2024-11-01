# audio_fingerprint.py

import numpy as np

FINGERPRINT_THRESHOLD = 0.8

def extract_features(audio_segment):
    # Convert AudioSegment to raw audio data
    samples = np.array(audio_segment.get_array_of_samples())
    # Simple feature extraction: average amplitude in a few frequency bands
    fft = np.fft.fft(samples)
    freq = np.fft.fftfreq(len(samples))
    bands = [0, 250, 500, 1000, 2000, 4000, 8000]  # Hz
    features = []
    for i in range(len(bands) - 1):
        band = fft[(freq >= bands[i]) & (freq < bands[i+1])]
        if band.size > 0:
            features.append(np.mean(np.abs(band)))
        else:
            features.append(0)  # Handle empty band case
    return np.array(features)

def compare_fingerprints(fp1, fp2):
    if fp1 is None or fp2 is None:
        return 0
    if len(fp1) != len(fp2):
        return 0
    dot_product = np.dot(fp1, fp2)
    norm_product = np.linalg.norm(fp1) * np.linalg.norm(fp2)
    similarity = dot_product / norm_product if norm_product != 0 else 0
    print(f"Dot product: {dot_product}, Norm product: {norm_product}, Similarity: {similarity}")
    return similarity

class AudioFingerprinter:
    def __init__(self):
        self.last_output_fingerprint = None

    def process_output(self, audio_segment):
        self.last_output_fingerprint = extract_features(audio_segment)

    def check_input(self, audio_data):
        input_fingerprint = extract_features(audio_data)
        similarity = compare_fingerprints(input_fingerprint, self.last_output_fingerprint)
        is_similar = similarity >= FINGERPRINT_THRESHOLD
        print(f"Input fingerprint similarity: {similarity}, is similar: {is_similar}")
        return not is_similar
