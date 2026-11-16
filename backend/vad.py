import sys

import numpy as np
import soundfile as sf
import torch
from silero_vad import load_silero_vad

torch.set_num_threads(1)
model = load_silero_vad()

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_MS = FRAME_SAMPLES * 1000 // SAMPLE_RATE

def speech_prob(frame_bytes: bytes) -> float:
    """Probability (0 to 1) that this 32 ms frame contains speech."""
    samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return model(torch.from_numpy(samples), SAMPLE_RATE).item()

def reset() -> None:
    """Clear the model's memory before a new audio stream."""
    model.reset_states()

if __name__ == "__main__":
    audio, rate = sf.read(sys.argv[1], dtype="int16")
    assert rate == SAMPLE_RATE, f"expected 16 kHz, got {rate}"
    data = audio.tobytes()

    reset()
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        p = speech_prob(data[i : i + FRAME_BYTES])
        ms = (i // FRAME_BYTES) * FRAME_MS
        bar = "#" * int(p * 40)
        print(f"{ms:6d} ms: {p:.2f} {bar}")