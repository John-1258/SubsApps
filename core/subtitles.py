# core/subtitles.py

def format_timestamp(seconds: float) -> str:
    """
    Safe SRT timestamp formatter.
    Fixes the ",1000" millisecond bug caused by rounding fractional seconds.
    """
    seconds = 0.0 if seconds is None else float(seconds)
    if seconds < 0:
        seconds = 0.0

    total_ms = int(round(seconds * 1000.0))  # whole milliseconds
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def segments_to_srt(segments):
    """
    segments: list of dicts with keys:
      - start (float seconds)
      - end (float seconds)
      - sub1 (str)
      - sub2 (str, optional)
    """
    srt_lines = []

    for i, seg in enumerate(segments, start=1):
        # sanitize timing at the last step too (cheap safety)
        s = float(seg.get("start", 0.0) or 0.0)
        e = float(seg.get("end", s) or s)
        if s < 0:
            s = 0.0
        if e < s:
            e = s

        start = format_timestamp(s)
        end = format_timestamp(e)

        sub1 = (seg.get("sub1") or "").strip()
        sub2 = (seg.get("sub2") or "").strip()

        srt_lines.append(str(i))
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(sub1 if sub1 else "")
        if sub2:
            srt_lines.append(sub2)
        srt_lines.append("")

    return "\n".join(srt_lines)