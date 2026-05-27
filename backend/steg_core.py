import numpy as np
import pywt
from scipy.fftpack import dct, idct

# Quantization step. Larger = more robust to re-encoding, slightly lower PSNR.
# Margin = SCALE * 0.25 — H.264 quantisation noise must stay below this to avoid bit flips.
# SCALE=36 → margin 9  → too small for ABR re-encoding (bits get flipped)
# SCALE=64 → margin 16 → survives typical H.264 ABR/CRF re-encoding reliably
# SCALE=36 gives ~40 dB PSNR; SCALE=64 gives ~37 dB — both perceptually transparent.
SCALE = 64
BLOCK = 4  # 4x4 DCT blocks inside the LL subband


def _dct2(block):
    return dct(dct(block.T, norm='ortho').T, norm='ortho')


def _idct2(block):
    return idct(idct(block.T, norm='ortho').T, norm='ortho')


def _dwt_ll(y):
    """1-level Haar DWT on the Y channel. Returns (LL, details, original_shape)."""
    LL, details = pywt.dwt2(y, 'haar')
    return LL, details


def ll_capacity(y):
    """
    How many bits can be embedded in this frame's LL subband.
    y must be a 2D float64 array (single channel).
    """
    LL, _ = _dwt_ll(y)
    h, w = LL.shape
    return (h // BLOCK) * (w // BLOCK)


def embed_bits(y, bits, offset):
    """
    Embed bits[offset:] into the Y channel using DWT -> DCT -> SVD.

    Pipeline per 4x4 block:
      1. Haar DWT  -> work in LL (low-frequency) subband only
      2. DCT       -> concentrate energy into fewer, larger coefficients
      3. SVD       -> S[0] is the most compression-stable scalar in the block
      4. Quantise S[0] to encode one bit:
            S[0] = (S[0] // SCALE + 0.25 + 0.5 * bit) * SCALE
         On decode: bit = int((S[0] % SCALE) > SCALE * 0.5)
         Weyl's theorem guarantees S[0] shifts by at most ||noise||_2 under
         additive perturbation, so SCALE=64 (margin=16) absorbs typical H.264 quantisation noise.

    Returns (modified_y as uint8, bits_consumed).
    """
    LL, (LH, HL, HH) = _dwt_ll(y)
    h, w = LL.shape
    ht = (h // BLOCK) * BLOCK
    wt = (w // BLOCK) * BLOCK
    n_row = ht // BLOCK
    n_col = wt // BLOCK
    count = min(len(bits) - offset, n_row * n_col)

    for i in range(count):
        r = (i // n_col) * BLOCK
        c = (i % n_col) * BLOCK
        block = LL[r:r + BLOCK, c:c + BLOCK].astype(np.float64)
        coeff = _dct2(block)
        U, S, Vt = np.linalg.svd(coeff)
        S[0] = (S[0] // SCALE + 0.25 + 0.5 * bits[offset + i]) * SCALE
        LL[r:r + BLOCK, c:c + BLOCK] = _idct2(U @ np.diag(S) @ Vt)

    orig_h, orig_w = y.shape
    reconstructed = pywt.idwt2((LL, (LH, HL, HH)), 'haar')
    reconstructed = np.clip(reconstructed[:orig_h, :orig_w], 0, 255)
    return reconstructed.astype(np.uint8), count


def extract_bits(y, count):
    """
    Extract `count` bits from the Y channel using the same DWT -> DCT -> SVD chain.
    Returns a list of ints (0 or 1).
    """
    LL, _ = _dwt_ll(y)
    h, w = LL.shape
    ht = (h // BLOCK) * BLOCK
    wt = (w // BLOCK) * BLOCK
    n_col = wt // BLOCK
    count = min(count, (ht // BLOCK) * n_col)

    bits = []
    for i in range(count):
        r = (i // n_col) * BLOCK
        c = (i % n_col) * BLOCK
        block = LL[r:r + BLOCK, c:c + BLOCK].astype(np.float64)
        coeff = _dct2(block)
        _, S, _ = np.linalg.svd(coeff)
        bits.append(int((S[0] % SCALE) > SCALE * 0.5))
    return bits
