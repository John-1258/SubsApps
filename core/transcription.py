# core/transcription.py

import os
from typing import Callable, Optional, Tuple

import whisper

from core.subtitles import segments_to_srt
from core.clean_subs import clean_segments
from core.groq_subtitle_ai import groq_batch_clean_split_translate
from core.device_profile import recommend_whisper_model
from core.media import is_audio, is_video, normalize_audio


_CURRENT_MODEL_NAME = None
_CURRENT_MODEL = None


ProgressCB = Optional[Callable[[int, str], None]]


def _emit(cb: ProgressCB, pct: int, stage: str):
    """Safe progress emitter."""
    if cb is None:
        return
    try:
        pct = int(max(0, min(100, pct)))
        cb(pct, stage)
    except Exception:
        # never break the pipeline because of UI callback
        pass


def get_model(name, progress_cb: ProgressCB = None):
    global _CURRENT_MODEL_NAME, _CURRENT_MODEL

    if name is None:
        name = recommend_whisper_model()

    if _CURRENT_MODEL is None or name != _CURRENT_MODEL_NAME:
        _emit(progress_cb, 8, f"Loading Whisper model: {name}")
        print(f"[Whisper] Loading model: {name}")
        _CURRENT_MODEL = whisper.load_model(name)
        _CURRENT_MODEL_NAME = name

    return _CURRENT_MODEL


def _norm_lang(code: str | None) -> str | None:
    """Normalize UI language codes."""
    if code is None:
        return None
    code = str(code).strip()
    return code if code else None


def _is_same_lang(a: str | None, b: str | None) -> bool:
    return (a or "").lower() == (b or "").lower()


def _progress_translate(base: int, span: int, done: int, total: int) -> int:
    """Map translate progress into a [base..base+span] range."""
    if total <= 0:
        return base
    frac = max(0.0, min(1.0, done / float(total)))
    return int(round(base + span * frac))


def transcribe_audio_path(
    input_path: str,
    model_name=None,
    whisper_lang=None,          # UI: what Whisper listens as (None => auto detect)
    first_lang="zh",            # UI: line1 output language
    second_lang=None,           # UI: line2 output language
    use_clean_segments=False,   # OFF by default to preserve raw timing
    translate_batch_size=1,     # 1 = safest, can bump to 5/10 later
    repair_missing=True,        # retry missing translations once
    progress_cb: ProgressCB = None
):
    """
    Progress behavior (safe, no timing changes):
      0–10%   setup / model load
      10–60%  Whisper (stage-based, no fine-grain possible)
      60–95%  Groq translate loop (real progress)
      95–99%  Repair missing lines (real progress)
      100%    done
    """

    _emit(progress_cb, 1, "Starting")

    filename = (input_path or "").lower()
    whisper_lang = _norm_lang(whisper_lang)
    first_lang = _norm_lang(first_lang)
    second_lang = _norm_lang(second_lang)

    model = get_model(model_name, progress_cb=progress_cb)

    temp_path = None
    try:
        _emit(progress_cb, 10, "Preparing media")

        if is_video(filename):
            source_for_whisper = input_path
        elif is_audio(filename):
            # normalizing audio can take time; show a stage
            _emit(progress_cb, 12, "Normalizing audio")
            temp_path = normalize_audio(input_path)
            source_for_whisper = temp_path
        else:
            raise ValueError("Unsupported file type")

        _emit(progress_cb, 18, "Whisper transcribing")

        # CLI-like deterministic decode
        opts = dict(
            task="transcribe",
            temperature=0.0,
            condition_on_previous_text=True,
        )
        if whisper_lang is not None:
            opts["language"] = whisper_lang

        # NOTE: whisper has no progress callback here (unfortunately)
        result = model.transcribe(source_for_whisper, **opts)

        _emit(progress_cb, 60, "Whisper done")

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    raw_segments = result.get("segments") or []

    # preserve raw timing by default
    segments_for_output = clean_segments(raw_segments) if use_clean_segments else raw_segments

    # Decide whether we need AI for sub1/sub2
    need_ai_sub1 = first_lang is not None and (whisper_lang is None or not _is_same_lang(first_lang, whisper_lang))
    need_ai_sub2 = second_lang is not None

    final_segments = []

    # If no AI needed at all: just output Whisper as line1
    if not need_ai_sub1 and not need_ai_sub2:
        _emit(progress_cb, 95, "No translation needed; building SRT")
        for seg in segments_for_output:
            final_segments.append({
                "start": float(seg.get("start", 0.0) or 0.0),
                "end": float(seg.get("end", 0.0) or 0.0),
                "sub1": (seg.get("text") or "").strip(),
                "sub2": "",
            })
        _emit(progress_cb, 100, "Done")
        return {"text": result.get("text", ""), "srt": segments_to_srt(final_segments)}

    # Translate per-cue (or small batches), but NEVER change timing
    total_segs = len(segments_for_output)
    done_segs = 0

    batch_texts, batch_segs = [], []

    def apply_ai_results_to_segments(segs, ai_results):
        nonlocal final_segments, done_segs

        if not isinstance(ai_results, list):
            ai_results = []
        if len(ai_results) < len(segs):
            ai_results = ai_results + [{} for _ in range(len(segs) - len(ai_results))]

        for idx, seg0 in enumerate(segs):
            ai = ai_results[idx] if isinstance(ai_results[idx], dict) else {}
            src = (seg0.get("text") or "").strip()

            # sub1
            if need_ai_sub1:
                sub1_lines = ai.get("sub1_lines") or []
                sub1_lines = [s.strip() for s in sub1_lines if isinstance(s, str) and s.strip()]
                sub1 = " ".join(sub1_lines).strip() if sub1_lines else src
            else:
                sub1 = src

            # sub2
            if need_ai_sub2:
                sub2_lines = ai.get("sub2_lines") or []
                sub2_lines = [s.strip() for s in sub2_lines if isinstance(s, str) and s.strip()]
                sub2 = " ".join(sub2_lines).strip() if sub2_lines else ""
            else:
                sub2 = ""

            final_segments.append({
                "start": float(seg0.get("start", 0.0) or 0.0),
                "end": float(seg0.get("end", 0.0) or 0.0),
                "sub1": sub1,
                "sub2": sub2,
            })

            done_segs += 1
            pct = _progress_translate(60, 35, done_segs, total_segs)  # 60..95
            _emit(progress_cb, pct, "Translating")

    groq_first = first_lang if need_ai_sub1 else (whisper_lang or first_lang or "zh")

    _emit(progress_cb, 60, "Translating")

    for seg in segments_for_output:
        txt = (seg.get("text") or "").strip()
        batch_texts.append(txt)
        batch_segs.append(seg)

        if len(batch_texts) == translate_batch_size:
            ai_results = groq_batch_clean_split_translate(
                batch_texts,
                first_lang=groq_first,
                second_lang=second_lang
            )
            apply_ai_results_to_segments(batch_segs, ai_results)
            batch_texts, batch_segs = [], []

    if batch_texts:
        ai_results = groq_batch_clean_split_translate(
            batch_texts,
            first_lang=groq_first,
            second_lang=second_lang
        )
        apply_ai_results_to_segments(batch_segs, ai_results)

    _emit(progress_cb, 95, "Translation pass done")

    # Repair missing cue-by-cue (the “call groq one more time” behavior)
    if repair_missing and (need_ai_sub2 or need_ai_sub1):
        to_fix = []
        for i, cue in enumerate(final_segments):
            if need_ai_sub2 and not (cue.get("sub2") or "").strip():
                to_fix.append(i)
            elif need_ai_sub1 and not (cue.get("sub1") or "").strip():
                to_fix.append(i)

        if to_fix:
            print(f"[repair] retrying {len(to_fix)} missing lines...")
            _emit(progress_cb, 95, f"Repairing missing lines ({len(to_fix)})")

        total_fix = len(to_fix)
        for k, i in enumerate(to_fix, start=1):
            src = (segments_for_output[i].get("text") or "").strip()
            ai_results = groq_batch_clean_split_translate(
                [src],
                first_lang=groq_first,
                second_lang=second_lang
            )

            if isinstance(ai_results, list) and ai_results:
                ai = ai_results[0] if isinstance(ai_results[0], dict) else {}

                if need_ai_sub1 and not (final_segments[i].get("sub1") or "").strip():
                    sub1_lines = ai.get("sub1_lines") or []
                    sub1_lines = [s.strip() for s in sub1_lines if isinstance(s, str) and s.strip()]
                    if sub1_lines:
                        final_segments[i]["sub1"] = " ".join(sub1_lines).strip()

                if need_ai_sub2 and not (final_segments[i].get("sub2") or "").strip():
                    sub2_lines = ai.get("sub2_lines") or []
                    sub2_lines = [s.strip() for s in sub2_lines if isinstance(s, str) and s.strip()]
                    if sub2_lines:
                        final_segments[i]["sub2"] = " ".join(sub2_lines).strip()

            # map repair progress into 95..99
            if total_fix > 0:
                pct = 95 + int(round(4 * (k / float(total_fix))))
                _emit(progress_cb, pct, "Repairing")

    _emit(progress_cb, 99, "Building SRT")

    srt_text = segments_to_srt(final_segments)
    _emit(progress_cb, 100, "Done")
    return {"text": result.get("text", ""), "srt": srt_text}