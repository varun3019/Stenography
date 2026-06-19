import numpy as np
from crypto_utils import generate_key, decrypt_bytes
from steg_core import ll_capacity, extract_bits
from video_utils import load_video

HEADER_BITS = 32


def _bits_to_bytes(bits: list) -> bytes:
    data = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        data.append(byte)
    return bytes(data)


def extract_data(input_path, password):
    frames, _, _ = load_video(input_path)
    key = generate_key(password)

    all_bits = []
    total_needed = None

    for frame in frames:
        if total_needed is not None and len(all_bits) >= total_needed:
            break

        channel = frame[:, :, 0].astype(np.float64)
        cap = ll_capacity(channel)

        if total_needed is None:
            all_bits.extend(extract_bits(channel, cap))

            if len(all_bits) >= HEADER_BITS:
                payload_length = 0
                for b in all_bits[:HEADER_BITS]:
                    payload_length = (payload_length << 1) | b

                max_possible = sum(
                    ll_capacity(f[:, :, 0].astype(np.float64)) for f in frames
                ) - HEADER_BITS
                if payload_length <= 0 or payload_length > max_possible:
                    raise ValueError("No hidden data found or wrong password")

                total_needed = HEADER_BITS + payload_length
        else:
            remaining = total_needed - len(all_bits)
            all_bits.extend(extract_bits(channel, min(remaining, cap)))

    if total_needed is None or len(all_bits) < total_needed:
        raise ValueError("No hidden data found")

    encrypted = _bits_to_bytes(all_bits[HEADER_BITS:total_needed])
    return decrypt_bytes(encrypted, key)
