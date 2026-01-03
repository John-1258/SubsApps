import subprocess
import tempfile
#import OS system 
import os

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm")

#find what the files ends with 
def is_audio(filename: str) -> bool:
    return filename.lower().endswith(AUDIO_EXTENSIONS)

def is_video(filename: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS)



#convert audio to 16K Hz for whisper to run 
def normalize_audio(input_path: str) -> str:
    #output the file as wav
    output = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = output.name
    #close the output so it can be edit
    output.close()

    #use command promits to activates ffmpeg
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        output_path
    ]

    #run command promits with out returning any message
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

#Extract audio from video and normalize it
def extract_audio_from_video(video_path: str) -> str:

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    output_path = output.name
    output.close()

    #use command promits to get audio from video
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        output_path
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return output_path