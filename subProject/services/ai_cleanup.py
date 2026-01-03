from openai import OpenAI

client = OpenAI()

def clean_word_live(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return text

    prompt = f"""
You are a live subtitle editor.

Fix grammar and phrasing ONLY.
Do NOT change meaning.
Do NOT add words.
Do NOT change srt format
Keep it short and natural.

Text:
"{text}"

Return ONLY the corrected sentence.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional subtitle editor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=60
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("AI cleanup error:", e)
        return text
