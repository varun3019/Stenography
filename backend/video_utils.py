import subprocess
import cv2
import numpy as np
import imageio_ffmpeg


def load_video(path):
    cap = cv2.VideoCapture(path)
    frames = []
    fps = cap.get(cv2.CAP_PROP_FPS)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return np.array(frames), fps, len(frames)


def save_video(frames, output_path, fps):
    """
    Encode frames to H.264 MP4 using FFmpeg at CRF=23.

    CRF=23 is H.264's default quality level — it targets consistent visual
    quality rather than a fixed bitrate. This is required for DWT+DCT+SVD
    bit survival: ABR (bitrate-targeted) encoding can quantise aggressively
    on long/low-bitrate videos, which exceeds the embedding margin and flips bits.
    Output size will be close to any video originally encoded at CRF 20-26.
    """
    if len(frames) == 0:
        raise ValueError("No frames to save")
    h, w = frames[0].shape[:2]

    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{w}x{h}',
        '-pix_fmt', 'bgr24',
        '-r', str(fps),
        '-i', 'pipe:',
        '-c:v', 'libx264',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg encoding failed:\n{stderr.decode()}")
