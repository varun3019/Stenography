import cv2
import numpy as np
from crypto_utils import generate_key, encrypt_bytes
from steg_core import ll_capacity, embed_bits
from video_utils import load_video, save_video

# 32-bit header stores the payload length in bits so the decoder
# knows exactly how many bits to pull out across frames.
HEADER_BITS = 32


def _to_bits(data: bytes) -> list:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _length_header(n_bits: int) -> list:
    return [(n_bits >> i) & 1 for i in range(HEADER_BITS - 1, -1, -1)]


def embed_data(input_path, data, password, output_path):
    key = generate_key(password)
    encrypted = encrypt_bytes(data, key)

    payload_bits = _length_header(len(encrypted) * 8) + _to_bits(encrypted)

    frames, fps, _ = load_video(input_path)

    # Verify the video has enough capacity before touching anything.
    total_capacity = sum(
        ll_capacity(cv2.cvtColor(f, cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.float64))
        for f in frames
    )
    if len(payload_bits) > total_capacity:
        raise ValueError(
            f"Payload too large: need {len(payload_bits)} bits "
            f"but video holds {total_capacity} bits ({total_capacity // 8} bytes)."
        )

    result = []
    bit_idx = 0

    for frame in frames:
        if bit_idx >= len(payload_bits):
            result.append(frame)
            continue

        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        y = ycrcb[:, :, 0].astype(np.float64)

        modified_y, consumed = embed_bits(y, payload_bits, bit_idx)
        bit_idx += consumed

        ycrcb[:, :, 0] = modified_y
        result.append(cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR))

    save_video(result, output_path, fps)
