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
        '-crf', '0',
        '-pix_fmt', 'yuv444p',
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
