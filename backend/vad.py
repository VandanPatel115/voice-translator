import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512                  # 32 ms at 16 kHz
FRAME_BYTES = FRAME_SAMPLES * 2      # 2 bytes per 16-bit sample
FRAME_MS = FRAME_SAMPLES * 1000 // SAMPLE_RATE
CONTEXT_SAMPLES = 64                 # Silero glues the previous 64 samples onto each frame

MODEL_PATH = Path(__file__).with_name("models") / "silero_vad.onnx"

_options = ort.SessionOptions()
_options.intra_op_num_threads = 1
_options.inter_op_num_threads = 1
_session = ort.InferenceSession(
    str(MODEL_PATH), sess_options=_options, providers=["CPUExecutionProvider"]
)


class SileroVAD:
    """Speech probability for 32 ms frames. One instance per audio stream."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, CONTEXT_SAMPLES), dtype=np.float32)

    def __call__(self, frame_bytes: bytes) -> float:
        samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        x = np.concatenate([self.context, samples.reshape(1, -1)], axis=1)
        prob, self.state = _session.run(
            None,
            {"input": x, "state": self.state, "sr": np.array(SAMPLE_RATE, dtype=np.int64)},
        )
        self.context = x[:, -CONTEXT_SAMPLES:]
        return float(prob[0][0])


if __name__ == "__main__":
    import soundfile as sf

    audio, rate = sf.read(sys.argv[1], dtype="int16")
    assert rate == SAMPLE_RATE, f"expected 16 kHz, got {rate}"
    data = audio.tobytes()

    vad = SileroVAD()
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        p = vad(data[i:i + FRAME_BYTES])
        ms = (i // FRAME_BYTES) * FRAME_MS
        print(f"{ms:6d} ms  {p:.2f}  {'█' * int(p * 40)}")