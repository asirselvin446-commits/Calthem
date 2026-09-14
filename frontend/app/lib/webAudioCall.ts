/**
 * WebVoiceCall — browser client for a Bolna web voice call.
 *
 * Protocol (see bolna DefaultInput/OutputHandler):
 *   send:  {type:"audio", data:<base64 16kHz mono PCM16>}  (mic)
 *          {type:"text",  data:"..."}                        (typed fallback)
 *   recv:  {type:"audio", data:<base64 24kHz mono PCM16>}   (AI voice)
 *          {type:"text",  data:"..."}                        (AI words)
 *          {type:"clear"}                                    (barge-in: stop playback)
 *          {type:"mark"|"ack"|...}                            (ignored)
 *
 * Mic uses a 16 kHz AudioContext so the browser resamples for us; playback uses
 * a separate 24 kHz AudioContext with scheduled buffers for gapless audio.
 */

export type CallHandlers = {
  onStatus?: (status: string) => void;
  onAiText?: (text: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (msg: string) => void;
};

function floatTo16BitPCM(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function base64FromBytes(bytes: Uint8Array): string {
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + chunk)) as any);
  }
  return btoa(bin);
}

function bytesFromBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export class WebVoiceCall {
  private ws: WebSocket | null = null;
  private micCtx: AudioContext | null = null;
  private playCtx: AudioContext | null = null;
  private micStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private nextStart = 0;
  private scheduled: AudioBufferSourceNode[] = [];
  private micOn = false;
  private closed = false;

  constructor(private wsUrl: string, private handlers: CallHandlers) {}

  async connect(): Promise<void> {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.onopen = () => {
      this.handlers.onOpen?.();
      try { this.ws?.send(JSON.stringify({ type: "init", meta_data: {} })); } catch {}
    };
    this.ws.onmessage = (ev) => this.onMessage(ev);
    this.ws.onerror = () => this.handlers.onError?.("Connection error");
    this.ws.onclose = () => { if (!this.closed) this.handlers.onClose?.(); };

    this.playCtx = new AudioContext({ sampleRate: 24000 });
    // Some browsers start the context suspended until a user gesture.
    if (this.playCtx.state === "suspended") { try { await this.playCtx.resume(); } catch {} }
  }

  private onMessage(ev: MessageEvent) {
    let msg: any;
    try { msg = JSON.parse(ev.data); } catch { return; }
    switch (msg.type) {
      case "audio":
        if (msg.data) this.playChunk(msg.data);
        this.handlers.onStatus?.("ai_speaking");
        break;
      case "text":
        if (msg.data) this.handlers.onAiText?.(String(msg.data));
        break;
      case "clear":
        this.stopPlayback();
        this.handlers.onStatus?.("listening");
        break;
      default:
        break; // mark / ack / pre_mark_message — ignore
    }
  }

  private playChunk(b64: string) {
    if (!this.playCtx) return;
    let bytes = bytesFromBase64(b64);
    if (bytes.length % 2 !== 0) bytes = bytes.subarray(0, bytes.length - 1);
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.length / 2);
    const f32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 0x8000;

    const buf = this.playCtx.createBuffer(1, f32.length, 24000);
    buf.copyToChannel(f32, 0);
    const src = this.playCtx.createBufferSource();
    src.buffer = buf;
    src.connect(this.playCtx.destination);

    const now = this.playCtx.currentTime;
    if (this.nextStart < now) this.nextStart = now + 0.03;
    src.start(this.nextStart);
    this.nextStart += buf.duration;
    this.scheduled.push(src);
    src.onended = () => {
      this.scheduled = this.scheduled.filter((s) => s !== src);
    };
  }

  private stopPlayback() {
    for (const s of this.scheduled) { try { s.stop(); } catch {} }
    this.scheduled = [];
    this.nextStart = 0;
  }

  async startMic(): Promise<void> {
    if (this.micOn) return;
    this.micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    this.micCtx = new AudioContext({ sampleRate: 16000 });
    if (this.micCtx.state === "suspended") { try { await this.micCtx.resume(); } catch {} }
    this.source = this.micCtx.createMediaStreamSource(this.micStream);
    this.processor = this.micCtx.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (e) => {
      if (!this.micOn || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm = floatTo16BitPCM(input);
      const b64 = base64FromBytes(new Uint8Array(pcm.buffer));
      try { this.ws.send(JSON.stringify({ type: "audio", data: b64 })); } catch {}
    };
    this.source.connect(this.processor);
    this.processor.connect(this.micCtx.destination);
    this.micOn = true;
    this.handlers.onStatus?.("listening");
  }

  stopMic() {
    this.micOn = false;
    try { this.processor?.disconnect(); } catch {}
    try { this.source?.disconnect(); } catch {}
    try { this.micStream?.getTracks().forEach((t) => t.stop()); } catch {}
    try { this.micCtx?.close(); } catch {}
    this.processor = null; this.source = null; this.micStream = null; this.micCtx = null;
  }

  sendText(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "text", data: text }));
    }
  }

  close() {
    this.closed = true;
    this.stopMic();
    this.stopPlayback();
    try { this.playCtx?.close(); } catch {}
    try { this.ws?.close(); } catch {}
    this.ws = null; this.playCtx = null;
  }
}
