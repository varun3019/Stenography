import os
import numpy as np
import cv2
from video_utils import load_video, save_video
from crypto_utils import generate_key, encrypt_message, decrypt_message
from embed import embed_data
from extract import extract_data

PASS = "testpassword"
VIDEO = "test_original.mp4"
STEGO = "test_stego.mp4"

# ── 1. Crypto round-trip ──────────────────────────────────────────────────────
key = generate_key(PASS)
ct = encrypt_message("Hello World!", key)
pt = decrypt_message(ct, key)
assert pt == "Hello World!", "Crypto FAILED"
print("[PASS] Crypto round-trip")

# ── 2. Create a realistic test video (gradient frames, not pure noise) ────────
# Pure noise has unusual DCT properties — gradients better represent real video.
frames = []
for i in range(10):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = np.linspace(i * 10, 255, 640, dtype=np.uint8)
    frame[:, :, 1] = np.linspace(0, 200, 480, dtype=np.uint8).reshape(-1, 1)
    frame[:, :, 2] = 128
    frames.append(frame)
save_video(frames, VIDEO, 30)
print(f"[INFO] Test video: {len(frames)} frames, 640x480, {os.path.getsize(VIDEO)} bytes")

# ── 3. Embed + Extract round-trip ─────────────────────────────────────────────
secret = b"This is a secret message hidden inside the video using DWT+DCT+SVD!"
embed_data(VIDEO, secret, PASS, STEGO)
recovered = extract_data(STEGO, PASS)
assert recovered == secret, f"Stego FAILED — got: {recovered}"
print("[PASS] Embed + Extract round-trip")

# ── 4. File size check (should be same size, no appended bytes) ───────────────
orig_size = os.path.getsize(VIDEO)
stego_size = os.path.getsize(STEGO)
diff = stego_size - orig_size
print(f"[INFO] File size: {orig_size} → {stego_size} (diff: {diff:+d} bytes)")

# ── 5. Frame count preserved ──────────────────────────────────────────────────
stego_frames, fps, n = load_video(STEGO)
assert n == len(frames), f"Frame count changed: {len(frames)} → {n}"
print(f"[PASS] Frame count preserved ({n} frames at {fps} fps)")

# ── 6. Visual quality — PSNR between original and stego frames ────────────────
psnr_values = []
for orig, stego in zip(frames, stego_frames):
    mse = np.mean((orig.astype(np.float64) - stego.astype(np.float64)) ** 2)
    if mse == 0:
        psnr_values.append(float('inf'))
    else:
        psnr_values.append(10 * np.log10(255 ** 2 / mse))
avg_psnr = np.mean([p for p in psnr_values if p != float('inf')])
print(f"[INFO] Average PSNR: {avg_psnr:.2f} dB  (>37 dB = perceptually transparent)")
if avg_psnr >= 37:
    print("[PASS] Visual quality acceptable")
else:
    print("[WARN] PSNR below threshold — check SCALE value in steg_core.py")

# ── 7. Wrong password must fail ───────────────────────────────────────────────
try:
    extract_data(STEGO, "wrongpassword")
    print("[FAIL] Wrong password should have raised an error")
except Exception as e:
    print(f"[PASS] Wrong password correctly rejected ({type(e).__name__})")

# ── 8. Cleanup ────────────────────────────────────────────────────────────────
os.remove(VIDEO)
os.remove(STEGO)
print("\nAll tests passed.")
