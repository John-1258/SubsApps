#Make segments into readable text
SHORT_UTTERANCES = {
    "嗯", "哦", "啊", "呀", "好", "係", "得", "冇",
    "yes", "no", "ok", "okay", "yeah"
}

PAUSE_THRESHOLD = 0.8

def clean_segments(
    segments,
    min_chars=8,
    max_chars=40,
    max_duration=6.0
):
    
    clean = []
    buffer_text = ""
    start_time = None
    end_time = None


    for seg in segments:
        text = seg["text"].strip()
        #check if text is empty
        if not text:
            continue

        seg_start = seg["start"]
        seg_end = seg["end"]


        #check if start time is empty
        if start_time is None:
            buffer_text = text 
            start_time = seg_start
            end_time = seg_end
            continue

        pause = seg_start - end_time

        #check if singler words
        if text.lower() in SHORT_UTTERANCES:
            clean.append({
                "start": start_time,
                "end": end_time,
                "text": buffer_text
            })
            buffer_text = text
            start_time = seg_start
            end_time = seg_end
            continue

        duration = end_time - start_time
        
        #check if got pause or not 
        if pause >= PAUSE_THRESHOLD:
            clean.append({
                "start": start_time,
                "end": end_time,
                "text": buffer_text
            })
            buffer_text = text
            start_time = seg_start
            end_time = seg_end
            continue

        
        #check too long split
        if(len(buffer_text) >= max_chars or duration >= max_duration ):
            clean.append({
                "start": start_time,
                "end": end_time,
                "text": buffer_text.strip()
            })

            buffer_text = text
            start_time = seg_start
            end_time = seg_end

        #split with signs
        if buffer_text.endswith(("?", "!", "。", "？", "！", ", ")):
            clean.append({
                "start": start_time,
                "end": end_time,
                "text": buffer_text.strip()
            })
            buffer_text = text
            start_time = seg_start
            end_time = seg_end
            continue


        #otherwise merge
        buffer_text += " " + text
        end_time = seg_end

    if buffer_text and start_time is not None and end_time is not None:
        clean.append({
            "start": start_time,
            "end": end_time,
            "text": buffer_text.strip()
        })

    return clean