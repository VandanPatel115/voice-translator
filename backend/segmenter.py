import io
import sys
from collections import deque

import numpy as np
import soundfile as sf

from backend.vad import FRAME_BYTES, FRAME_MS, SAMPLE_RATE, reset, speech_prob


class Segmenter:
    """Cuts a stream of 32 ms frames into separate utterances at pauses."""

    def __init__(
        self,
        start_threshold: float = 0.5,
        end_threshold: float = 0.35,
        start_frames: int = 2,
        end_silence_ms: int = 50,
        pre_roll_ms: int = 200,
        min_speech_ms: int = 300,
        max_utterance_ms: int = 12000,
        keep_trailing_ms: int = 200,
    ):
        self.start_threshold = start_threshold
        self.end_threshold = end_threshold
        self.start_frames = start_frames
        self.end_silence_frames = end_silence_ms // FRAME_MS
        self.min_speech_frames = min_speech_ms // FRAME_MS
        self.max_frames = max_utterance_ms // FRAME_MS
        self.keep_trailing = keep_trailing_ms // FRAME_MS
        self.pre_roll = deque(maxlen=pre_roll_ms // FRAME_MS)
        self._reset_state()

    def _reset_state(self) -> None:
        self.state = "SILENT"
        self.frames: list[bytes] = []
        self.speech_run = 0
        self.silence_run = 0
        self.voiced_frames = 0

    def feed(self, frame: bytes) -> bytes | None:
        """Add one frame. Returns a finished utterance, or None."""
        p = speech_prob(frame)

        if self.state == "SILENT":
            self.pre_roll.append(frame)
            self.speech_run = self.speech_run + 1 if p >= self.start_threshold else 0
            if self.speech_run >= self.start_frames:
                self.state = "SPEAKING"
                self.frames = list(self.pre_roll)
                self.pre_roll.clear()
                self.voiced_frames = self.speech_run
                self.silence_run = 0
            return None

        # state == "SPEAKING"
        self.frames.append(frame)
        if p < self.end_threshold:
            self.silence_run += 1
        else:
            self.silence_run = 0
            self.voiced_frames += 1

        if self.silence_run >= self.end_silence_frames or len(self.frames) >= self.max_frames:
            return self._finish()
        return None

    def _finish(self) -> bytes | None:
        trailing_to_drop = max(0, self.silence_run - self.keep_trailing)
        frames = self.frames[: len(self.frames) - trailing_to_drop]
        voiced = self.voiced_frames
        self._reset_state()
        if voiced < self.min_speech_frames:
            return None
        return b"".join(frames)


def pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw 16-bit PCM in a WAV header, in memory."""
    buf = io.BytesIO()
    sf.write(buf, np.frombuffer(pcm, dtype=np.int16), SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


if __name__ == "__main__":
    from backend.asr import transcribe

    # Join several recordings with 1 s of silence between them, like one long stream
    silence = bytes(SAMPLE_RATE * 2)
    stream = b""
    for path in sys.argv[1:]:
        audio, _ = sf.read(path, dtype="int16")
        stream += audio.tobytes() + silence

    reset()
    seg = Segmenter()
    count = 0
    for i in range(0, len(stream) - FRAME_BYTES + 1, FRAME_BYTES):
        utterance = seg.feed(stream[i:i + FRAME_BYTES])
        if utterance:
            count += 1
            seconds = len(utterance) / (SAMPLE_RATE * 2)
            text = transcribe(pcm_to_wav(utterance))
            print(f"Utterance {count}: {seconds:.2f} s → {text}")