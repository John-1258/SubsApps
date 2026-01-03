from services.translation import translate_to_english

#convert time to str format
def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def split_text_into_lines(text, max_chars=14):
    """
    Split long Chinese text into readable subtitle lines.
    """
    words = text.split(" ")
    lines = []
    current = ""

    for w in words:
        if len(current.replace(" ", "")) + len(w) <= max_chars:
            if current:
                current += " " + w
            else:
                current = w
        else:
            lines.append(current)
            current = w

    if current:
        lines.append(current)

    return lines


#take a segment to become srt
def segments_to_srt(segments):
    srt_lines = []

    for i, seg in enumerate(segments, start=1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])

        zh_text = seg["text"].strip()
        en_text = translate_to_english(zh_text)

        zh_lines = split_text_into_lines(zh_text)
        en_lines = split_text_into_lines(en_text)

        srt_lines.append(str(i))
        srt_lines.append(f"{start} --> {end}")

        # add Chinese lines
        for line in zh_lines:
            srt_lines.append(line)

        # add English lines
        for line in en_lines:
            srt_lines.append(line)

        srt_lines.append("")  # blank line between blocks

    return "\n".join(srt_lines)
