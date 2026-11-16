import os
import sys
import time

from backend.asr import transcribe
from backend.translate import translate
from backend.tts import synthesize

def run_file(path: str) -> None:
    """English WAV in, Hindi WAV out, with per-stage timing."""
    with open(path, "rb") as f:
        audio_in = f.read()

    t0 = time.perf_counter()
    english = transcribe(audio_in)
    t1 = time.perf_counter()
    hindi = translate(english)
    t2 = time.perf_counter()
    audio_out = synthesize(hindi)
    t3 = time.perf_counter()

    name = os.path.splitext(os.path.basename(path))[0]
    os.makedirs("out", exist_ok=True)
    out_path = f"out/{name}_hi.wav"
    with open(out_path, "wb") as f:
        f.write(audio_out) 


    ms = lambda a, b: (b - a) * 1000
    print(f"== {name}")
    print(f"   EN: {english}")
    print(f"   HI: {hindi}")
    print(f"   ASR {ms(t0, t1):.0f} ms | MT {ms(t1, t2):.0f} ms | "
          f"TTS {ms(t2, t3):.0f} ms | total {ms(t0, t3):.0f} ms")
    print(f"   → {out_path}\n")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        run_file(path)