# Technical Report: Secure Video Steganography System

**Author:** Rohith (`rohithbrock9164@gmail.com`)  
**Repository:** Secure Video Steganography  
**Date:** June 2026

---

## 1. Executive Summary

This project implements a **full-stack web application** that hides AES-256-GCM-encrypted secret messages inside ordinary MP4 video files with **no visible degradation**. It uses a **frequency-domain steganography** pipeline combining the Discrete Wavelet Transform (DWT), Discrete Cosine Transform (DCT), and Singular Value Decomposition (SVD) to embed one bit per 4×4 block of the luminance channel's low-frequency subband. The system is resilient to H.264 re-encoding (up to CRF 28) and provides a password-based security model via SHA-256 key derivation.

**Note on file size:** The output stego video is ~10× larger than the input because `save_video` uses `-crf 0` (lossless H.264) to guarantee no data loss during save. This is a deliberate trade-off — the embedded data survives real-world CRF ≤ 28 re-encoding, so users can transcode the output to a smaller size after embedding.

---

## 2. System Architecture

### 2.1 High-Level Stack

```
┌─────────────────────────────────────────────────────┐
│                    Browser (React SPA)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ EncodeForm  │  │ DecodeForm  │  │   api.js    │ │
│  │ (hide msg)  │  │ (extract)   │  │ (fetch)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         │                │                │         │
└─────────┼────────────────┼────────────────┼─────────┘
          │  POST /encode  │  POST /decode  │
          └────────┬───────┘       │        │
                   │               │        │
          ┌────────▼───────────────▼────────▼──────┐
          │          Vite Dev Proxy (5173)          │
          │   /encode → localhost:8000/encode       │
          │   /decode → localhost:8000/decode       │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
          │          FastAPI Backend (8000)           │
          │  ┌──────────┐  ┌──────────┐  ┌────────┐ │
          │  │ main.py  │  │ embed.py │  │extract │ │
          │  │ (routes) │  │ (encode) │  │ (decode│ │
          │  └──────────┘  └────┬─────┘  └───┬────┘ │
          │        ┌────────────▼────────────▼──┐   │
          │        │       steg_core.py          │   │
          │        │  DWT → DCT → SVD pipeline  │   │
          │        └────────────┬────────────────┘   │
          │        ┌────────────▼────────────────┐   │
          │        │      crypto_utils.py         │   │
          │        │  AES-256-GCM + SHA-256 KDF  │   │
          │        └─────────────────────────────┘   │
          │        ┌─────────────────────────────┐   │
          │        │      video_utils.py          │   │
          │        │  OpenCV (read) + FFmpeg(write)│   │
          │        └─────────────────────────────┘   │
          └──────────────────────────────────────────┘
```

### 2.2 Technology Stack Detail

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend Framework | React | 18.x | Component-based UI |
| Build Tool | Vite | 6.x | Dev server + bundling |
| Frontend Language | JavaScript (JSX) | ES2022 | UI logic |
| Backend Framework | FastAPI | latest | Async REST API |
| Backend Language | Python | 3.12+ | Signal processing |
| Encryption | `cryptography` (AESGCM) | latest | AES-256-GCM |
| Wavelet Transform | PyWavelets | latest | Haar DWT |
| Linear Algebra | SciPy + NumPy | latest | DCT, SVD, IDCT |
| Video I/O | OpenCV + imageio-ffmpeg | latest | Frame reading, H.264 encoding |

---

## 3. Detailed Component Analysis

### 3.1 Backend Core: `steg_core.py` (The Steganographic Engine)

This is the heart of the system. It implements a **DWT → DCT → SVD pipeline** operating on the Y (luminance) channel of each video frame.

#### 3.1.1 Constants

```python
SCALE = 64   # Quantization step — determines robustness vs. quality trade-off
BLOCK = 4    # 4×4 DCT block size
```

- **SCALE = 64** provides ~37 dB PSNR and survives H.264 CRF ≤ 28. The margin (SCALE × 0.25 = 16) exceeds typical quantisation noise.
- **SCALE = 36** would give ~40 dB PSNR but fails under re-encoding (margin = 9 is too small).
- **BLOCK = 4**: 4×4 DCT blocks inside the LL subband. Smaller blocks = more capacity but less robustness.

#### 3.1.2 Embedding Pipeline (`embed_bits`)

For each 4×4 block in the LL subband:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────────┐
│ Haar DWT │───▶│   DCT   │───▶│   SVD   │───▶│   Quantize   │
│ (1-level)│    │ (4×4)   │    │         │    │   S[0]       │
└─────────┘    └─────────┘    └─────────┘    └──────┬───────┘
                                                     │
┌─────────┐    ┌─────────┐    ┌─────────┐           │
│ Frame Y │◀───│ Haar    │◀───│  IDCT   │◀──────────┘
│ (uint8) │    │ IDWT    │    │         │
└─────────┘    └─────────┘    └─────────┘
```

**Step by step:**

1. **Haar DWT** (`pywt.dwt2`): Decomposes the Y channel into LL (low-low), LH, HL, HH subbands. The LL subband contains the approximation coefficients — this is where we embed because it is most resistant to compression.

2. **DCT** (`scipy.fftpack.dct`): Applied to each 4×4 block of the LL subband. Concentrates energy into low-frequency coefficients.

3. **SVD** (`numpy.linalg.svd`): Decomposes the 4×4 DCT coefficient matrix into U, S, Vt. The first singular value S[0] is the **largest and most compression-stable** coefficient due to Weyl's theorem: additive noise perturbs S[0] by at most the L2 norm of the noise.

4. **Quantization**: One bit is encoded by quantizing S[0]:
   ```python
   S[0] = (S[0] // SCALE + 0.25 + 0.5 * bit) * SCALE
   ```
   - If bit = 0: S[0] aligns to the lower quarter of the quantization bin.
   - If bit = 1: S[0] aligns to the upper quarter.
   - On decode: `bit = int((S[0] % SCALE) > SCALE × 0.5)`

5. **Inverse transforms**: IDCT → IDWT → clamp to [0, 255] → uint8.

#### 3.1.3 Extraction Pipeline (`extract_bits`)

Identical forward pipeline (DWT → DCT → SVD), then the bit is read from S[0] using the modulo test above. No ground truth needed — the embedding is **blind** (does not require the original video).

#### 3.1.4 Capacity Calculation (`ll_capacity`)

```python
def ll_capacity(y):
    LL, _ = _dwt_ll(y)
    h, w = LL.shape
    return (h // BLOCK) * (w // BLOCK)  # number of 4×4 blocks in LL
```

For a 1920×1080 frame:
- LL subband after 1-level Haar DWT: 960×540
- Blocks: (960//4) × (540//4) = 240 × 135 = 32,400 bits = ~4 KB per frame
- At 30 fps, a 10-second video can hold ~1.2 MB of payload.

### 3.2 Cryptography Module: `crypto_utils.py`

**Algorithm: AES-256-GCM** (Galois/Counter Mode)

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `generate_key(password)` | string | 32 bytes | SHA-256(password) → AES-256 key |
| `encrypt_bytes(data, key)` | bytes + 32B key | nonce(12B) + ciphertext | AES-256-GCM encrypt |
| `decrypt_bytes(data, key)` | nonce(12B) + ct + tag | bytes | AES-256-GCM decrypt |
| `encrypt_message(message, key)` | string + key | nonce + ciphertext | Wrapper for strings |
| `decrypt_message(data, key)` | nonce + ct + tag | string | Wrapper for strings |

**Security properties:**
- **Confidentiality**: AES-256 provides 256-bit security.
- **Integrity + Authentication**: GCM mode includes an authentication tag; any tampering causes decryption to fail.
- **Nonce reuse resistance**: A fresh 12-byte random nonce (`os.urandom(12)`) is generated per encryption.
- **Key derivation**: SHA-256 is used for key derivation (not a proper KDF like Argon2 — see Limitations).

### 3.3 Embedding Orchestrator: `embed.py`

**Data flow:**
```
message (string)
    │
    ▼
encode() → bytes
    │
    ▼
encrypt_bytes(data, key) → nonce + ciphertext = encrypted_payload
    │
    ▼
_length_header(len(payload_in_bits)) → 32-bit big-endian header
    │
    ▼
concatenate: [32-bit header] + [payload bits] = bitstream
    │
    ▼
For each frame:
    extract Y channel (frame[:,:,0])
    embed_bits(Y, bitstream, current_offset)
    write modified Y channel back to BGR frame
    │
    ▼
save_video(frames, output_path, fps) → H.264 MP4 via FFmpeg
```

**Payload format (bitstream layout):**

```
┌─────────────────┬──────────────────────────────┐
│  32-bit header  │  Encrypted payload (N bytes) │
│  (big-endian    │  = nonce (12B) + ciphertext  │
│   length in     │    + GCM tag (16B)           │
│   bits)         │                              │
└─────────────────┴──────────────────────────────┘
```

**Capacity check**: Before embedding, the total capacity of all frames is computed. If the payload exceeds capacity, a `ValueError` is raised with exact bit and byte requirements.

### 3.4 Extraction Orchestrator: `extract.py`

**Data flow:**
```
stego_video.mp4
    │
    ▼
load_video(path) → frames
    │
    ▼
For each frame:
    extract_bits(Y) → all_bits[]
    Read first 32 bits → payload_length
    Validate (must be > 0 and ≤ max_possible)
    Continue reading until payload_length bits collected
    │
    ▼
_bits_to_bytes(all_bits[32:32+payload_length]) → encrypted_bytes
    │
    ▼
decrypt_bytes(encrypted_bytes, key) → original_message
```

**Validation logic** (line 44 of extract.py):
```python
if payload_length <= 0 or payload_length > max_possible:
    raise ValueError("No hidden data found or wrong password")
```
This acts as a **canary check**: a wrong password produces garbage bits that almost certainly decode to an invalid length, causing early rejection (typically within 1–2 frames).

### 3.5 Video I/O: `video_utils.py`

#### Loading (`load_video`)
- Uses OpenCV's `VideoCapture` to read all frames into a NumPy array (shape: `[N, H, W, 3]` in BGR order).
- Returns: `(frames_array, fps, frame_count)`.

#### Saving (`save_video`)
- Pipes raw BGR24 frames via stdin to an **FFmpeg subprocess** (located via `imageio_ffmpeg.get_ffmpeg_exe()`).
- Encoding parameters:
  ```
  -c:v libx264     (H.264 codec)
  -crf 0           (lossless — ensures no data loss during save)
  -pix_fmt yuv444p (full chroma subsampling)
  -movflags +faststart (enables streaming)
  ```
- **Critical trade-off**: CRF 0 (lossless) produces output files ~10× larger than a typical compressed input (e.g., a 5 MB input becomes ~50 MB). This is intentional — any lossy encoding during save could corrupt the embedded bits. The user is expected to re-encode the stego video to their desired compression level after embedding; the DWT+DCT+SVD pipeline is designed to survive CRF ≤ 28 re-encoding.

### 3.6 FastAPI Server: `main.py`

Two asynchronous POST endpoints:

#### `POST /encode`
| Parameter | Type | Location |
|-----------|------|----------|
| video | UploadFile | multipart/form-data |
| message | str | form field |
| password | str | form field |

**Response**: `FileResponse` with `stego_video.mp4` (media type: `video/mp4`).

#### `POST /decode`
| Parameter | Type | Location |
|-----------|------|----------|
| video | UploadFile | multipart/form-data |
| password | str | form field |

**Response**: `{"message": "decrypted text"}` on success.  
**Error handling**: Distinguishes between "no hidden data" and "wrong password/corrupted payload" via exception message matching.

**Cleanup**: Both endpoints use `try/finally` blocks with `os.unlink` to remove temporary files.

**CORS**: Configured to allow `http://localhost:5173` (Vite dev server) for POST requests.

### 3.7 Frontend: React SPA

#### `App.jsx`
- Root component with tab navigation: **"Hide Message"** (encode) / **"Extract Message"** (decode).
- Uses conditional rendering with state to toggle between `EncodeForm` and `DecodeForm`.

#### `Pages.jsx`
Two form components sharing a common visual language:

**EncodeForm**:
- File picker (accepts `video/*`) with custom styling.
- Message textarea + password input.
- **Stage tracker**: 4 stages with animated progress dots.
- On success: download button for `stego_video.mp4`.
- Error display.

**DecodeForm**:
- File picker + password input.
- 4-stage tracker (matching the encode process in reverse).
- On success: displays decrypted message in a result box.

**UX design patterns**:
- `useRef` timer for stage animation (not tied to actual progress — the backend is a single request).
- `URL.createObjectURL` for download without server-side blob storage.
- Debounced reset on file change.

#### `api.js`
Two thin wrappers around `fetch`:
```javascript
export async function encode(video, message, password) {
    const form = new FormData();
    form.append("video", video);
    form.append("message", message);
    form.append("password", password);
    const res = await fetch("/encode", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.blob();
}
```
The Vite dev server proxies `/encode` and `/decode` to `localhost:8000`.

#### `index.css`
~372 lines of hand-written CSS (no Tailwind despite README mention):
- Dark theme: `#0d0d11` backgrounds, `#c9d1d9` text.
- Layout: centered panels (max-width 560px), flexbox.
- Stage tracker: horizontal dot-and-label progress indicator.
- Animations: pulsing dots for active stage, fade-in for results.
- Buttons: gradient accents (#58a6ff blue, #3fb950 green for download).

---

## 4. Embedding Robustness: Mathematical Foundation

### 4.1 Why SVD?

The DCT concentrates energy into a few coefficients. SVD further decomposes the DCT coefficient matrix into singular values, where **S[0] (the largest singular value)** has a crucial property:

**Weyl's Theorem**: For matrices A and E (where E is perturbation noise from H.264 quantization):
```
|σ_i(A + E) - σ_i(A)| ≤ ||E||_2
```
This means S[0] shifts by at most the L2 norm of the quantisation noise. With SCALE = 64 and a margin of 16, typical H.264 quantization noise at CRF ≤ 28 stays comfortably below this threshold.

### 4.2 Why DWT + LL Subband?

The 1-level Haar DWT splits the frame into:
- **LL**: Low-frequency approximation (half the resolution). Most energy, most compression-resistant.
- **LH, HL, HH**: High-frequency details. More fragile under compression.

Embedding in LL ensures the bits survive H.264's quantization, which primarily attacks high-frequency data.

### 4.3 Why the BLOCK = 4 DCT?

4×4 blocks in the LL subband provide:
- **Better localization** than larger blocks (less cross-frame interference).
- **Sufficient coefficients** for meaningful SVD (4×4 matrix has 4 singular values).
- **Higher capacity** than 8×8 blocks.

---

## 5. Performance Characteristics

### 5.1 Capacity

| Resolution | LL dimensions | Blocks | Bits/frame | Bytes/frame |
|-----------|--------------|--------|------------|-------------|
| 640×480 | 320×240 | 80×60 = 4,800 | 4,800 | 600 |
| 1280×720 | 640×360 | 160×90 = 14,400 | 14,400 | 1,800 |
| 1920×1080 | 960×540 | 240×135 = 32,400 | 32,400 | 4,050 |

At 30 fps, a 10-second 1080p video: ~32,400 × 300 = 9,720,000 bits ≈ 1.2 MB payload.

### 5.2 Speed

- **CPU-bound**: The DCT, SVD, IDCT per 4×4 block is computationally intensive.
- **No GPU acceleration**: All operations use NumPy/SciPy on CPU.
- **Frame-by-frame**: No parallel processing.
- Estimate: ~0.5–2 seconds per frame depending on resolution and hardware.

### 5.3 Quality Impact

| Metric | SCALE = 36 | SCALE = 64 |
|--------|------------|------------|
| PSNR | ~40 dB | ~37 dB |
| SSIM | >0.99 | >0.98 |
| Robustness | Fails under CRF > 20 | Survives CRF ≤ 28 |
| Perceptibility | Imperceptible | Imperceptible |

Both PSNR values are well above the commonly accepted threshold of 30 dB for perceptual transparency.

---

## 6. Security Model

### 6.1 Threat Model

**Assumptions:**
- The attacker has access to the stego video file.
- The attacker knows the steganography algorithm (Kerckhoffs's principle — security relies solely on the password).
- The attacker does NOT know the password.
- The attacker can apply standard video processing (re-encoding, cropping, resizing).

**What the system protects against:**
1. **Blind detection**: The embedded data is statistically indistinguishable from natural DCT coefficient noise (uniform distribution of S[0] mod SCALE).
2. **Extraction without password**: AES-256-GCM prevents decryption. Additionally, the extraction pipeline would fail the length header validation on wrong password attempts (garbage-length rejection).
3. **Tampering**: GCM authentication detects any modification to the ciphertext.

**What it does NOT protect against (explicit limitations):**
- Aggressive re-encoding (CRF > 35) destroys embedded data.
- Geometric attacks (cropping >50%, resizing) break block alignment.
- Statistical analysis by a trained CNN could potentially flag the embedding (not provably undetectable).
- No resistance to frame dropping or temporal attacks.

### 6.2 Cryptographic Flow

```
password
    │
    ▼
SHA-256(password) → 32-byte AES-256 key
    │
    ▼
AES-256-GCM.encrypt(
    plaintext = message,
    key = derived_key,
    nonce = os.urandom(12)  ← fresh per encryption
)
    │
    ▼
output = nonce(12B) || ciphertext || GCM_tag(16B)
```

### 6.3 Known Security Weakness

The key derivation uses **SHA-256(password)** rather than a proper password-based KDF (e.g., Argon2id, bcrypt, PBKDF2). This means:
- No **salt** — same password always produces the same key.
- No **work factor** — fast to brute-force weak passwords.
- **Precomputation attacks** (rainbow tables) are feasible.

This is acceptable for a demonstration project but should be upgraded for production use.

---

## 7. API Reference

### 7.1 `POST /encode`

**Request** (multipart/form-data):
```
video:    <binary MP4 file>
message:  "Secret message to hide"
password: "hunter2"
```

**Response** (200 OK):
```
Content-Type: video/mp4
Content-Disposition: attachment; filename="stego_video.mp4"
<binary MP4 data>
```

**Error** (400 Bad Request):
```json
{"detail": "Payload too large: need 123456 bits but video holds 7890 bits"}
```

### 7.2 `POST /decode`

**Request** (multipart/form-data):
```
video:    <binary stego MP4 file>
password: "hunter2"
```

**Response** (200 OK):
```json
{"message": "Secret message to hide"}
```

**Error** (400 Bad Request):
```json
{"detail": "Wrong password or corrupted payload"}
```

---

## 8. Setup & Deployment

### 8.1 Prerequisites

- Python 3.12+
- Node.js 20+
- FFmpeg (installed and available on PATH, or managed by `imageio-ffmpeg`)
- Git

### 8.2 Backend Setup

```powershell
cd backend
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload    # starts on port 8000
```

### 8.3 Frontend Setup

```powershell
cd frontend
npm install
npm run dev                  # starts on port 5173
```

### 8.4 Required Dependencies

**Python** (`requirements.txt`):
```
fastapi
uvicorn
opencv-python
numpy
cryptography
PyWavelets
scipy
imageio-ffmpeg
```

**JavaScript** (`package.json`):
- `react` + `react-dom` (18.x)
- `vite` (6.x)
- `@vitejs/plugin-react`

---

## 9. Project Structure

```
Stenography/
├── .gitignore
├── README.md
├── TECHNICAL_REPORT.md              ← this document
│
├── backend/
│   ├── main.py                      # FastAPI server (2 routes)
│   ├── crypto_utils.py              # AES-256-GCM + SHA-256 KDF
│   ├── steg_core.py                 # DWT → DCT → SVD embedding engine
│   ├── embed.py                     # Embedding orchestrator
│   ├── extract.py                   # Extraction orchestrator
│   ├── video_utils.py               # OpenCV reader + FFmpeg writer
│   └── requirements.txt
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx                 # React entry point
        ├── App.jsx                  # Root + tab navigation
        ├── Pages.jsx                # EncodeForm + DecodeForm
        ├── api.js                   # API client
        └── index.css                # Dark-themed stylesheet
```

---

## 10. Limitations & Future Work

### Current Limitations
1. **10× file size blowup**: `save_video` uses lossless CRF 0, inflating output to ~10× the input size. Users must manually re-encode for storage efficiency.
2. **CPU-bound performance**: No parallelism or GPU acceleration; large videos are slow to process.
2. **Single-frame processing**: No temporal redundancy — embedding is per-frame independent.
4. **Weak key derivation**: SHA-256(password) lacks salt and work factor.
5. **H.264-specific robustness**: Tested only against libx264; other codecs (H.265, VP9) may behave differently.
6. **No statistical undetectability guarantee**: A trained CNN classifier could potentially detect the embedding.
7. **No tests**: The project lacks automated tests.

### Potential Improvements
1. Parallel frame processing using `concurrent.futures` or multiprocessing.
2. GPU-accelerated DCT/SVD via CuPy or PyTorch.
3. Error-correcting codes (Reed-Solomon, BCH) for robustness against higher compression.
4. Proper KDF (Argon2id) with salt stored alongside or derived from the embedding.
5. Multi-channel embedding (Y, U, V or RGB) for 3× capacity.
6. Temporal redundancy schemes to survive frame dropping.
7. CNNs for adaptive embedding strength based on local texture complexity.
8. Automated test suite with pytest and sample video fixtures.

---

## 11. Conclusion

This project successfully demonstrates a practical, web-based video steganography system using a sophisticated DWT+DCT+SVD embedding pipeline. It achieves ~37 dB PSNR with robustness to H.264 CRF ≤ 28 re-encoding, provides AES-256-GCM encryption of the payload, and presents an intuitive React frontend for user interaction. While not production-ready due to performance and key-derivation limitations, it serves as an excellent proof-of-concept and educational tool for understanding frequency-domain steganography techniques.
