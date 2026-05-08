# core/groq_subtitle_ai.py

import json
import re
from groq import Groq

from core.config import get_groq_key
from core.quota import check_and_consume

client = Groq(api_key=get_groq_key())

MODEL = "llama-3.1-8b-instant"
SYSTEM = "You are a professional subtitle translator. Return JSON only."

LANG_NAME = {
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "yue": "Cantonese",
    "ar": "Arabic",
}

# --- Script validators ---
_SCRIPT_RE = {
    "zh": re.compile(r"[\u4E00-\u9FFF]"),
    "yue": re.compile(r"[\u4E00-\u9FFF]"),
    "ja": re.compile(r"[\u3040-\u30FF\u4E00-\u9FFF]"),
    "ko": re.compile(r"[\uAC00-\uD7AF]"),
    "ar": re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
}

_LATIN_RE = re.compile(r"[A-Za-z]")
_LATIN_LANGS = {"en", "fr", "de", "es", "it", "pt", "nl", "sv", "no", "da", "fi", "pl", "tr", "id", "ms", "vi"}


def _safe_json_array(raw: str):
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            return None
    return None


def _max_chars_for(lang_code: str | None) -> int:
    if lang_code in ("zh", "yue", "ja", "ko"):
        return 14
    return 42


def _looks_like_lang(text: str, lang_code: str | None) -> bool:
    if not lang_code:
        return True
    text = (text or "").strip()
    if not text:
        return False

    rx = _SCRIPT_RE.get(lang_code)
    if rx:
        return bool(rx.search(text))

    if lang_code in _LATIN_LANGS:
        return bool(_LATIN_RE.search(text))

    return True


def _join_lines(lines):
    return " ".join([s.strip() for s in (lines or []) if isinstance(s, str) and s.strip()]).strip()


def _call_groq(prompt: str, temperature: float, max_tokens: int) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def _build_hard_rule_for_lang(lang_code: str | None, lang_label: str | None) -> str:
    if not lang_code or not lang_label:
        return ""
    if lang_code == "ja":
        return "HARD RULE: Output MUST contain Japanese characters (Hiragana/Katakana/Kanji). Romaji-only is NOT allowed."
    if lang_code == "ko":
        return "HARD RULE: Output MUST contain Hangul (한글)."
    if lang_code in ("zh", "yue"):
        return "HARD RULE: Output MUST contain Chinese characters (漢字)."
    if lang_code == "ar":
        return "HARD RULE: Output MUST contain Arabic script (العربية). Do NOT use Latin letters."
    if lang_code in _LATIN_LANGS:
        return f"HARD RULE: Output MUST be {lang_label} and MUST contain Latin letters (A–Z)."
    return f"HARD RULE: Output MUST be written in {lang_label}. If uncertain, still output best-effort {lang_label}."


def _repair_one_line_to_second_lang_with_context(
    prev_text: str,
    cur_text: str,
    next_text: str,
    second_lang: str,
    second_label: str,
    sub2_max: int
) -> list[str]:
    hard_rule = _build_hard_rule_for_lang(second_lang, second_label)

    prompt = f"""
Translate ONLY the CURRENT subtitle line into NATURAL {second_label}.

Context (for meaning only; DO NOT translate prev/next):
PREV: {prev_text}
CUR:  {cur_text}
NEXT: {next_text}

Rules:
- Keep meaning; do NOT add new info
- sub2_lines MUST NOT be empty
- 1–2 lines, each <= {sub2_max} chars
- Return JSON ONLY:
{{ "sub2_lines": ["..."] }}

{hard_rule}
""".strip()

    check_and_consume(1)
    raw = _call_groq(prompt, temperature=0.0, max_tokens=350)

    try:
        obj = json.loads(raw)
    except Exception:
        return []

    if isinstance(obj, dict):
        sub2 = [s.strip() for s in obj.get("sub2_lines", []) if isinstance(s, str) and s.strip()][:2]
        if sub2 and _looks_like_lang(_join_lines(sub2), second_lang):
            return sub2
    return []


def _repair_one_line_to_second_lang(
    text: str,
    second_lang: str,
    second_label: str,
    sub2_max: int
) -> list[str]:
    hard_rule = _build_hard_rule_for_lang(second_lang, second_label)

    prompt = f"""
Translate this subtitle line into NATURAL {second_label}.

Rules:
- Keep meaning; do NOT add new info
- sub2_lines MUST NOT be empty
- 1–2 lines, each <= {sub2_max} chars
- Return JSON ONLY:
{{ "sub2_lines": ["..."] }}

Input:
{text}

{hard_rule}
""".strip()

    check_and_consume(1)
    raw = _call_groq(prompt, temperature=0.0, max_tokens=300)

    try:
        obj = json.loads(raw)
    except Exception:
        return []

    if isinstance(obj, dict):
        sub2 = [s.strip() for s in obj.get("sub2_lines", []) if isinstance(s, str) and s.strip()][:2]
        if sub2 and _looks_like_lang(_join_lines(sub2), second_lang):
            return sub2
    return []


def _translate_batch_once(texts, second_lang: str):
    """
    Single Groq call for a batch. Returns by_id map or None.
    """
    n = len(texts)
    second_label = LANG_NAME.get(second_lang, second_lang)
    sub2_max = _max_chars_for(second_lang)
    hard2 = _build_hard_rule_for_lang(second_lang, second_label)

    numbered = "\n".join([f"[ID={i}] {texts[i]}" for i in range(n)])

    prompt = f"""
Translate EACH input line into NATURAL {second_label}.

Rules:
- Keep meaning; do NOT add new info
- Do NOT merge across IDs
- Keep numbers/proper nouns as much as possible
- sub2_lines MUST NOT be empty
- 1–2 lines, each <= {sub2_max} chars

Return JSON ARRAY ONLY (no markdown).
Each item:
- id: integer (0..{n-1})
- sub2_lines: ["...", "..."]

{hard2}

Input:
{numbered}
""".strip()

    check_and_consume(1)
    raw = _call_groq(prompt, temperature=0.0, max_tokens=2500)
    data = _safe_json_array(raw)
    if not isinstance(data, list):
        return None

    by_id = {}
    for it in data:
        if not isinstance(it, dict):
            continue
        rid = it.get("id")
        try:
            rid = int(rid)
        except Exception:
            continue
        by_id[rid] = it

    if len(by_id) < n:
        return None
    return by_id


def _translate_batch_resilient(texts, second_lang: str, max_batch: int = 10):
    """
    Resilient translator:
      - try whole chunk
      - if fails, split into halves until <= max_batch then give up
    """
    n = len(texts)
    results = [{"sub1_lines": [texts[i]], "sub2_lines": []} for i in range(n)]

    by_id = _translate_batch_once(texts, second_lang)
    if by_id is not None:
        for i in range(n):
            item = by_id.get(i, {})
            sub2_lines = item.get("sub2_lines") or []
            sub2_lines = [s.strip() for s in sub2_lines if isinstance(s, str) and s.strip()]
            if len(sub2_lines) > 2:
                sub2_lines = [sub2_lines[0], " ".join(sub2_lines[1:]).strip()]
            sub2_lines = sub2_lines[:2]
            if sub2_lines and not _looks_like_lang(_join_lines(sub2_lines), second_lang):
                sub2_lines = []
            results[i]["sub2_lines"] = sub2_lines
        return results

    if n <= max_batch:
        # give up; let repair handle
        return results

    mid = n // 2
    left = _translate_batch_resilient(texts[:mid], second_lang, max_batch=max_batch)
    right = _translate_batch_resilient(texts[mid:], second_lang, max_batch=max_batch)
    return left + right


def groq_batch_clean_split_translate(
    texts,
    first_lang="zh",   # kept for compatibility; mode 1 ignores it
    second_lang=None
):
    texts = [(t or "").strip() for t in (texts or [])]
    n = len(texts)
    if n == 0:
        return []
    if not any(texts):
        return [{"sub1_lines": [""], "sub2_lines": []} for _ in texts]

    if not second_lang:
        return [{"sub1_lines": [t], "sub2_lines": []} for t in texts]

    # 1) batch translate (proper batching)
    results = _translate_batch_resilient(texts, second_lang, max_batch=10)

    # 2) repair missing/invalid
    second_label = LANG_NAME.get(second_lang, second_lang)
    sub2_max = _max_chars_for(second_lang)

    bad_idxs = []
    for i in range(n):
        joined = _join_lines(results[i].get("sub2_lines") or [])
        if not joined or not _looks_like_lang(joined, second_lang):
            bad_idxs.append(i)

    if bad_idxs:
        print(f"[groq] repairing {len(bad_idxs)} missing/invalid {second_lang} lines...")

    for i in bad_idxs:
        prev_text = texts[i - 1] if i - 1 >= 0 else ""
        cur_text = texts[i]
        next_text = texts[i + 1] if i + 1 < n else ""

        repaired = _repair_one_line_to_second_lang_with_context(
            prev_text=prev_text,
            cur_text=cur_text,
            next_text=next_text,
            second_lang=second_lang,
            second_label=second_label,
            sub2_max=sub2_max
        )

        if not repaired:
            repaired = _repair_one_line_to_second_lang(
                text=cur_text,
                second_lang=second_lang,
                second_label=second_label,
                sub2_max=sub2_max
            )

        if repaired:
            results[i]["sub2_lines"] = repaired

    return results