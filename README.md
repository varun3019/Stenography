# Secure Video Steganography

Hide AES-GCM encrypted messages inside video frames using DWT + DCT + SVD frequency-domain embedding.

## Overview

This project hides encrypted data directly inside the luminance channel of video frames — no file size change, no structural anomalies, no visible difference. The embedded data is statistically indistinguishable from natural video noise and survives H.264 re-encoding. Only someone with the correct password can locate and decrypt the hidden payload.

### How It Works

**Encoding — per frame:**
1. The message is encrypted with AES-GCM (SHA-256 key derived from password)
2. A 32-bit header encoding the payload length is prepended to the encrypted bits
3. For each video frame, the Y (luminance) channel is extracted from YCrCb color space
4. A 1-level Haar DWT is applied — only the **LL (low-frequency approximation) subband** is used
5. The LL subband is split into 4×4 blocks. For each block:
   - Apply 2D DCT → concentrate energy into fewer large coefficients
   - Apply SVD → decompose the DCT matrix into U, S, Vt
   - Quantise **S[0]** (the largest, most compression-stable singular value) to encode one bit:
     `S[0] = (S[0] // 36 + 0.25 + 0.5 * bit) * 36`
   - Invert SVD → Invert DCT → write block back to LL
6. Invert DWT → reconstruct the Y channel → reassemble frame

**Decoding:**
1. Same DWT → DCT → SVD chain, read `S[0] % 36 > 18` per block to recover each bit
2. First 32 bits decoded → payload length, then extract that many bits
3. Reconstruct bytes → AES-GCM decrypt → original message

**Why S[0] survives H.264:**
Weyl's theorem bounds the perturbation of the largest singular value by `‖noise‖₂`. H.264 quantisation noise at CRF ≤ 28 stays well below the quantisation step of 36, so the embedded bit is preserved through re-encoding.

### Capacity

For a 1080p frame: LL subband ≈ 960×540 → 32,400 blocks → **32,400 bits per frame**.
A 30fps, 10-second video holds ~120 MB of payload capacity — far more than any practical message.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | FastAPI |
| Encryption | `cryptography` (AES-GCM) |
| Wavelet transform | `PyWavelets` (Haar DWT) |
| DCT / SVD | `scipy.fftpack`, `numpy.linalg` |

## Project Structure

```
Stenography/
├── backend/
│   ├── main.py           # FastAPI routes (/encode, /decode)
│   ├── crypto_utils.py   # AES-GCM encrypt/decrypt, key derivation
│   ├── steg_core.py      # DWT+DCT+SVD embed/extract primitives
│   ├── embed.py          # Frame-level embedding pipeline
│   ├── extract.py        # Frame-level extraction pipeline
│   ├── video_utils.py    # Video load/save (OpenCV)
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── App.jsx        # Root component with routing
    │   ├── Pages.jsx      # Encode and Decode page components
    │   ├── api.js         # Backend API calls
    │   └── index.css
    ├── index.html
    └── vite.config.js
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

## API Reference

### `POST /encode`

Embeds an encrypted message into a video.

| Field | Type | Description |
|---|---|---|
| `video` | file | Input MP4 video |
| `message` | string | Secret message to hide |
| `password` | string | Encryption password |

**Response:** Stego video file (MP4)

---

### `POST /decode`

Extracts and decrypts the hidden message from a stego video.

| Field | Type | Description |
|---|---|---|
| `video` | file | Stego MP4 video |
| `password` | string | Password used during encoding |

**Response:** `{ "message": "..." }`

## Security Model

| Layer | Mechanism | Purpose |
|---|---|---|
| Encryption | AES-GCM | Confidentiality, integrity, authentication |
| Key derivation | SHA-256(password) | Password → 256-bit key |
| Embedding domain | LL subband of Haar DWT | Low-frequency, compression-preserved region |
| Stability | SVD S[0] quantisation | Survives H.264 quantisation noise (Weyl's theorem) |
| Imperceptibility | PSNR ~40 dB, SSIM >0.98 | Changes invisible to human vision |

## Limitations

- **Processing time:** Every frame is decoded, transformed, and re-encoded. Large videos are slow on CPU.
- **Re-encoding at high CRF:** Survives H.264 at CRF ≤ 28. Aggressive compression (CRF > 35, social media transcoding) may corrupt the payload.
- **Geometric attacks:** Cropping or resizing the stego video beyond ~50% breaks extraction — block alignment is required.
- **Statistical detectability:** Reduces detectability significantly vs. container injection, but a CNN steganalysis model trained on this exact method could still flag it.
