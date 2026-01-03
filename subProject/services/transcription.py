import whisper
import tempfile
import shutil
from services.subtitles import segments_to_srt
from services.clean_subs import clean_segments
from services.media import (
    is_audio,
    is_video,
    normalize_audio,
    extract_audio_from_video
)


#select the model of whisper 
model = whisper.load_model("base")

async def transcribe_audio(file):

    #make py not to delete tempfile and generate .wav
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        #copy file to temp
        shutil.copyfileobj(file.file, temp)
        #take temp address
        input_path = temp.name

    #get the input filename
    filename = file.filename.lower()

    #check the properties of the file 
    if is_audio(filename):
        audio_path = normalize_audio(input_path)

    elif is_video(filename):
        audio_path = extract_audio_from_video(input_path)

    else:
        raise ValueError("Unsupported file type")

    #process in whisper
    result = model.transcribe(audio_path, language="zh")

    #get srt
    segments = clean_segments(result["segments"])
    srt_text = segments_to_srt(segments)

    return {
                "text": result["text"],
                "srt": srt_text
            }
 
