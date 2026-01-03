from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
from services.transcription import transcribe_audio
import numpy as np
import whisper
from services.ai_cleanup import clean_word_live


app = FastAPI()

#when someone visit (/)
@app.get("/")
#return message as alive
def health():
    return {"status": "Backend running"}

#direct to transcribe 
@app.post("/transcribe")
#use async to pause or wait the programme
async def transcribe(file: UploadFile = File(...)):

    #system waits for import files
    result = await transcribe_audio(file)


    #taking the result and make a downloadable art file, set name 
    return Response(
        content = result["srt"], 
        media_type = "application/x-subrip",
        headers={
            "Content-Disposition": "attachment; filename=subtitles.srt"
        })


#calculate the buffer size 
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
BUFFER_SECONDS = 3

TARGET_BUFFER_SIZE = SAMPLE_RATE * BYTES_PER_SAMPLE * BUFFER_SECONDS

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")  # start with base
print("Whisper loaded")

#make the websocket for live translation
@app.websocket("/ws/transcribe")
async def websocket_transcribe(ws: WebSocket):
    #wait for the connection
    await ws.accept()
    await ws.send_text("WebSocket connected")
    
    audio_buffer = bytearray()

    #make a loop to keep connecting the web
    try:
        while True:
            data = await ws.receive_bytes()
            
            #increase buffer size 
            audio_buffer.extend(data)

            #when buffer is full, move to next process
            if len(audio_buffer) >= TARGET_BUFFER_SIZE:
                print("Transcribing")

                #convert raw value to numbers byte -> int16 -> float32
                audio_np = np.frombuffer(audio_buffer, dtype=np.int16)
                audio_np = audio_np.astype(np.float32) / 32768.0

                #run the whisper
                result = whisper_model.transcribe(
                    audio_np,
                    language="en",
                    fp16=False
                )

                #if have result put in text if not empty
                raw_text = result.get("text", "").strip()

                #if there's text it waits and collect all the content
                if raw_text:
                    clean_text = clean_word_live(raw_text)

                    print("📝 RAW :", raw_text)
                    print("✨ CLEAN:", clean_text)

                    await ws.send_text(clean_text)


    except WebSocketDisconnect:
        print("Websocket Disconnected")
