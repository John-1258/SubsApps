SHORT_UTTERANCES = {
    "嗯", "哦", "啊", "呀", "好", "係", "得", "冇",
    "yes", "no", "ok", "okay", "yeah"
}

PAUSE_THRESHOLD = 0.8
END_PUNCT = ("?", "!", "。", "？", "！", "，", ",", "、", ";", "；", ":", "：")

def clean_segments(
    segments,
    min_chars=8,
    max_chars=40,
    max_duration=3.0,
    drop_short_utterances=True
):
    clean = []
    buffer_text = ""
    start_time = None
    end_time = None

    def flush():
        nonlocal buffer_text, start_time, end_time
        if buffer_text and start_time is not None and end_time is not None:
            text_out = buffer_text.strip()
            clean.append({"start": start_time, "end": end_time, "text": text_out})
        buffer_text = ""
        start_time = None
        end_time = None

    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        seg_start = float(seg["start"])
        seg_end = float(seg["end"])

        low = text.lower()

        if start_time is None:
            if drop_short_utterances and low in SHORT_UTTERANCES:
                continue
            buffer_text = text
            start_time = seg_start
            end_time = seg_end
            continue

        pause = max(0.0, seg_start - end_time)
        predicted_duration = seg_end - start_time
        predicted_len = len(buffer_text) + 1 + len(text)

        should_split = (
            pause >= PAUSE_THRESHOLD or
            predicted_len >= max_chars or
            predicted_duration >= max_duration or
            buffer_text.rstrip().endswith(END_PUNCT)
        )

        if should_split:
            flush()
            if drop_short_utterances and low in SHORT_UTTERANCES:
                continue
            buffer_text = text
            start_time = seg_start
            end_time = seg_end
            continue

        if low in SHORT_UTTERANCES:
            if not drop_short_utterances:
                buffer_text += " " + text
                end_time = seg_end
            continue

        buffer_text += " " + text
        end_time = seg_end

    flush()

    if min_chars and clean:
        merged = []
        for item in clean:
            if merged and len(item["text"]) < min_chars:
                prev = merged[-1]
                prev["text"] = (prev["text"] + " " + item["text"]).strip()
                prev["end"] = item["end"]
            else:
                merged.append(item)
        clean = merged

    return clean