const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");
const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const log = (text) => { logEl.textContent += text + "\n"; };

const FRAME_SAMPLES = 512;   // 32 ms at 16 kHz
let ws, audioCtx, stream;

let playCtx;
let nextStart = 0;
let streamRate = 22050;
let currentAudioId = null;
let mutedAudioId = null;
const activeSources = [];

function playPcmChunk(arrayBuffer) {
  const int16 = new Int16Array(arrayBuffer);
  const audioBuffer = playCtx.createBuffer(1, int16.length, streamRate);
  const channel = audioBuffer.getChannelData(0);
  for (let i = 0; i < int16.length; i++) {
    channel[i] = int16[i] / 32768;
  }

  const source = playCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(playCtx.destination);

  nextStart = Math.max(nextStart, playCtx.currentTime + 0.05);
  source.start(nextStart);
  nextStart += audioBuffer.duration;

  activeSources.push(source);
  source.onended = () => activeSources.splice(activeSources.indexOf(source), 1);
}

function stopPlayback() {
  activeSources.forEach((source) => {
    try { source.stop(); } catch (e) { /* already stopped */ }
  });
  activeSources.length = 0;
  nextStart = 0;
  mutedAudioId = currentAudioId;
}

function floatTo16BitPCM(floats) {
  const out = new Int16Array(floats.length);
  for (let i = 0; i < floats.length; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]));
    out[i] = s * 0x7FFF;
  }
  return out.buffer;
}

async function start() {
    playCtx = new AudioContext();
    nextStart = 0;
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      if (currentAudioId === mutedAudioId) return;
      playPcmChunk(event.data);
      return;
    }
    const msg = JSON.parse(event.data);
    if (msg.type === "vad") {
      statusEl.textContent = msg.speaking ? "🎙️ speaking…" : "listening";
      if (msg.speaking && activeSources.length > 0) {
        stopPlayback();
        log("✋ interrupted: playback stopped");
      }
    } else if (msg.type === "final_en") {
      log(`[${msg.id}] EN: ${msg.text}`);
    } else if (msg.type === "hindi") {
      log(`[${msg.id}] HI: ${msg.text}   (ASR ${msg.asr_ms} ms, MT ${msg.mt_ms} ms)`);
    } else if (msg.type === "audio_start") {
      streamRate = msg.sample_rate;
      currentAudioId = msg.id;
    } else if (msg.type === "audio_end") {
      log(`[${msg.id}] 🔊 TTS first audio ${msg.tts_first_ms} ms, total ${msg.tts_total_ms} ms`);
    } else if (msg.type === "error") {
      log(`⚠️ server error: ${msg.text}`);
    }
  };
  
  await new Promise((resolve) => (ws.onopen = resolve));
  log("connected");

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
    playCtx.close();
    ws.close();
    log("stopped");
    startBtn.disabled = false;
    stopBtn.disabled = true;
}

startBtn.onclick = start;
stopBtn.onclick = stop;
