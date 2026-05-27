import { useState, useRef } from "react";
import { encode, decode } from "./api.js";

const ENCODE_STAGES = [
  "Loading video frames",
  "Encrypting message with AES-256-GCM",
  "Embedding via DWT + DCT + SVD (per frame)",
  "Saving stego video",
];

const DECODE_STAGES = [
  "Loading stego video frames",
  "Extracting bits via DWT + DCT + SVD",
  "Reconstructing encrypted payload",
  "Decrypting with AES-256-GCM",
];

function StageTracker({ stages, activeStage, done }) {
  return (
    <div className="stages">
      <div className="stages-title">Process</div>
      {stages.map((label, i) => {
        const state = done || i < activeStage ? "done" : i === activeStage ? "active" : "pending";
        return (
          <div key={i} className={`stage stage-${state}`}>
            <div className="stage-dot">{state === "done" ? "✓" : ""}</div>
            <span className="stage-label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function FileZone({ file, onChange, id }) {
  return (
    <div className="file-zone">
      <input type="file" accept="video/*" onChange={onChange} required id={id} />
      <label htmlFor={id} className="file-label">
        {file ? (
          <div className="file-info">
            <span className="file-icon-sm">▶</span>
            <div>
              <div className="file-name">{file.name}</div>
              <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
            </div>
          </div>
        ) : (
          <div className="file-placeholder">
            <span className="file-icon">▶</span>
            <div>
              <div>Choose video file</div>
              <div className="file-hint">MP4, AVI, MOV…</div>
            </div>
          </div>
        )}
      </label>
    </div>
  );
}

export function EncodeForm() {
  const [video, setVideo] = useState(null);
  const [message, setMessage] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [blob, setBlob] = useState(null);
  const [activeStage, setActiveStage] = useState(-1);
  const [error, setError] = useState("");
  const timer = useRef(null);

  const reset = () => { setBlob(null); setActiveStage(-1); setError(""); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setBlob(null); setError(""); setActiveStage(0);
    let s = 0;
    timer.current = setInterval(() => {
      s++;
      if (s < ENCODE_STAGES.length - 1) setActiveStage(s);
      else clearInterval(timer.current);
    }, 700);
    try {
      const b = await encode(video, message, password);
      clearInterval(timer.current);
      setActiveStage(ENCODE_STAGES.length);
      setBlob(b);
    } catch (err) {
      clearInterval(timer.current);
      setError(err.message);
      setActiveStage(-1);
    }
    setLoading(false);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Hide a Message</h2>
        <p className="panel-sub">Encrypts your message and embeds it into the frequency domain of video frames — no visible change, no file size increase</p>
      </div>
      <form onSubmit={handleSubmit} className="form">
        <div className="field">
          <label>Cover video</label>
          <FileZone id="encode-file" file={video} onChange={(e) => { setVideo(e.target.files[0]); reset(); }} />
          {video && <div className="field-hint">Every frame is processed — larger videos take longer</div>}
        </div>
        <div className="field">
          <label>Secret message</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type the message to hide…"
            required
          />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Used to derive encryption key"
            required
          />
        </div>

        {(loading || activeStage >= 0) && (
          <StageTracker
            stages={ENCODE_STAGES}
            activeStage={activeStage}
            done={!loading && activeStage === ENCODE_STAGES.length}
          />
        )}

        {error && <div className="error-box">⚠ {error}</div>}

        {!loading && (
          <button type="submit" className="btn-primary">
            {activeStage === ENCODE_STAGES.length ? "Encode Again" : "Encode & Hide"}
          </button>
        )}

        {blob && (
          <a href={URL.createObjectURL(blob)} download="stego_video.mp4" className="btn-download">
            ↓ Download Stego Video
          </a>
        )}
      </form>
    </div>
  );
}

export function DecodeForm() {
  const [video, setVideo] = useState(null);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");
  const [activeStage, setActiveStage] = useState(-1);
  const [error, setError] = useState("");
  const timer = useRef(null);

  const reset = () => { setResult(""); setActiveStage(-1); setError(""); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setResult(""); setError(""); setActiveStage(0);
    let s = 0;
    timer.current = setInterval(() => {
      s++;
      if (s < DECODE_STAGES.length - 1) setActiveStage(s);
      else clearInterval(timer.current);
    }, 600);
    try {
      const json = await decode(video, password);
      clearInterval(timer.current);
      setActiveStage(DECODE_STAGES.length);
      setResult(json.message);
    } catch (err) {
      clearInterval(timer.current);
      setError(err.message);
      setActiveStage(-1);
    }
    setLoading(false);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Extract a Message</h2>
        <p className="panel-sub">Extracts hidden bits from the frequency domain of each frame and decrypts the payload</p>
      </div>
      <form onSubmit={handleSubmit} className="form">
        <div className="field">
          <label>Stego video</label>
          <FileZone id="decode-file" file={video} onChange={(e) => { setVideo(e.target.files[0]); reset(); }} />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Must match the encoding password"
            required
          />
        </div>

        {(loading || activeStage >= 0) && (
          <StageTracker
            stages={DECODE_STAGES}
            activeStage={activeStage}
            done={!loading && activeStage === DECODE_STAGES.length}
          />
        )}

        {error && <div className="error-box">⚠ {error}</div>}

        {!loading && (
          <button type="submit" className="btn-primary">
            {activeStage === DECODE_STAGES.length ? "Decode Again" : "Scan & Decode"}
          </button>
        )}

        {result && (
          <div className="result-box">
            <div className="result-label">Hidden message</div>
            <p className="result-text">{result}</p>
          </div>
        )}
      </form>
    </div>
  );
}
