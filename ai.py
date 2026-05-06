import json
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a fridge management assistant. 
Return ONLY a valid JSON object — no explanation, no markdown, no extra text.

Detect the intent from the user message and return one of these formats:

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
- add:     bought, got, picked up, added, purchased
- consume: used, finished, ate, drank, consumed
- throw:   threw, tossed, expired, binned, wasted
- view:    show, what's in, fridge, list, check

Rules:
- Match item names loosely to existing fridge contents where possible
- Default expiry: 7 days from today
- Default qty: 1
- Default category: fresh"""


def parse_intent(user_message: str, fridge_contents: list) -> dict:
    today = datetime.now().date().isoformat()
    contents_str = json.dumps(
        [dict(r) for r in fridge_contents], default=str
    ) if fridge_contents else "empty"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Today is {today}.\nFridge contents: {contents_str}\nMessage: \"{user_message}\""
        }]
    )

    return json.loads(response.content[0].text)
