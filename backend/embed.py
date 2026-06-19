import numpy as np
from crypto_utils import generate_key, encrypt_bytes
from steg_core import ll_capacity, embed_bits
from video_utils import load_video, save_video

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

    total_capacity = sum(
        ll_capacity(f[:, :, 0].astype(np.float64)) for f in frames
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

        channel = frame[:, :, 0].astype(np.float64)
        modified, consumed = embed_bits(channel, payload_bits, bit_idx)
        bit_idx += consumed

        frame[:, :, 0] = np.clip(modified, 0, 255).astype(np.uint8)
        result.append(frame)

    save_video(result, output_path, fps)
