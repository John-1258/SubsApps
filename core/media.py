# core/media.py
import os
import shutil
import subprocess
import tempfile

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm")


def is_audio(filename: str) -> bool:
    return filename.lower().endswith(AUDIO_EXTENSIONS)


def is_video(filename: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def _ensure_ffmpeg_available() -> str:
    """
    Return ffmpeg executable path if available, otherwise raise a clear error.
    """
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FileNotFoundError(
            "FFmpeg not found.\n\n"
            "This app needs ffmpeg.exe to read/convert audio/video.\n"
            "Fix options:\n"
            "1) Install FFmpeg and add it to PATH, OR\n"
            "2) Bundle ffmpeg.exe with the app (recommended for sharing)."
        )
    return exe


def normalize_audio(input_path: str) -> str:
    ffmpeg = _ensure_ffmpeg_available()

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = output.name
    output.close()

    cmd = [
        ffmpeg,
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        output_path
    ]

    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("FFmpeg failed to convert audio. Please check the input file and FFmpeg.")

    return output_path


def extract_audio_from_video(video_path: str) -> str:
    ffmpeg = _ensure_ffmpeg_available()

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = output.name
    output.close()

    cmd = [
        ffmpeg,
        "-y",
        "-i", video_path,
        "-map", "0:a:0",
        "-vn",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-af", "aresample=async=0:first_pts=0",
        output_path
    ]

    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("FFmpeg failed to extract audio from video. Please check the video file and FFmpeg.")

    return output_path