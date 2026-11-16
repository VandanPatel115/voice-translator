const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");
const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const log = (text) => { logEl.textContent += text + "\n"; };

const FRAME_SAMPLES = 512;   // 32 ms at 16 kHz
let ws, audioCtx, stream;

function floatTo16BitPCM(floats) {
  const out = new Int16Array(floats.length);
  for (let i = 0; i < floats.length; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]));
    out[i] = s * 0x7FFF;
  }
  return out.buffer;
}

async function start() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
    ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "vad") {
      statusEl.textContent = msg.speaking ? "🎙️ speaking…" : "listening";
    } else if (msg.type === "final_en") {
      log(`[${msg.id}] EN: ${msg.text}`);
    } else if (msg.type === "hindi") {
      log(`[${msg.id}] HI: ${msg.text}   (ASR ${msg.asr_ms} ms, MT ${msg.mt_ms} ms)`);
    }
  };

  stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  audioCtx = new AudioContext({ sampleRate: 16000 });
  await audioCtx.audioWorklet.addModule("pcm-worklet.js");

  const source = audioCtx.createMediaStreamSource(stream);
  const worklet = new AudioWorkletNode(audioCtx, "pcm-worklet");
  source.connect(worklet);

  let pending = [];
  worklet.port.onmessage = (event) => {
    pending.push(...event.data);
    while (pending.length >= FRAME_SAMPLES) {
      const frame = pending.splice(0, FRAME_SAMPLES);
      if (ws.readyState === WebSocket.OPEN) ws.send(floatTo16BitPCM(frame));
    }
  };

  log(`mic started, sample rate ${audioCtx.sampleRate} Hz`);
  startBtn.disabled = true;
  stopBtn.disabled = false;
}

function stop() {
  stream.getTracks().forEach((track) => track.stop());
  audioCtx.close();
  ws.close();
  log("stopped");
  startBtn.disabled = false;
  stopBtn.disabled = true;
}

startBtn.onclick = start;
stopBtn.onclick = stop;
