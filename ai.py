import json
from datetime import datetime
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL  = "gemini-3.1-flash-lite-preview"

SYSTEM_PROMPT = """You are a fridge management assistant.
Return ONLY a valid JSON array — no explanation, no markdown, no extra text.
Each element in the array is one action to perform.

Each element must be one of these formats:

Add item:
{"intent": "add", "item_name": "name", "qty": 1, "expiry": "YYYY-MM-DD", "category": "fresh|household|sauces"}

Consume item:
{"intent": "consume", "item_name": "name", "qty": 1}

Throw item:
{"intent": "throw", "item_name": "name"}

View fridge:
{"intent": "view"}

Unknown:
{"intent": "unknown"}

Intent keywords:
- add:     bought, got, picked up, added, purchased, buying
- consume: used, finished, ate, drank, consumed
- throw:   threw, tossed, expired, binned, wasted, spoiled
- view:    show, what's in, fridge, list, check

Rules:
- If the message mentions multiple items, return one array element per item
- Match item names loosely to existing fridge contents where possible
- Default expiry: 7 days from today
- Default qty: 1
- Default category: fresh
- Always return an array, even for a single action"""


def parse_intent(user_message: str, fridge_contents: list) -> list:
    today = datetime.now().date().isoformat()
    contents_str = json.dumps(
        [dict(r) for r in fridge_contents], default=str
    ) if fridge_contents else "empty"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Today is {today}.\n"
        f"Fridge contents: {contents_str}\n"
        f"Message: \"{user_message}\""
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="none"),
        temperature=0.1,
        max_output_tokens=512,
    )
    )

    cleaned = (
        response.text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(cleaned)