import json
from datetime import datetime
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL  = "gemini-2.0-flash-lite"

SYSTEM_PROMPT = """You are a fridge and pantry management assistant.
Return ONLY a valid JSON array — no explanation, no markdown, no extra text.
Each element in the array is one action to perform.
Each element must be one of these formats:

Add item:
{"intent": "add", "brand": "Brand Name or empty string if none", "item_name": "Product Name", "qty": 1, "expiry": "YYYY-MM-DD", "category": "fresh|frozen|dry goods|drinks|condiments|household|snacks"}

Consume item:
{"intent": "consume", "brand": "Brand Name or empty string if none", "item_name": "Product Name", "qty": 1}

Throw item:
{"intent": "throw", "brand": "Brand Name or empty string if none", "item_name": "Product Name"}

View fridge:
{"intent": "view"}

Unknown:
{"intent": "unknown"}

Intent keywords:
- add:     bought, got, picked up, added, purchased, buying, stocked
- consume: used, finished, ate, drank, consumed
- throw:   threw, tossed, expired, binned, wasted, spoiled
- view:    show, what's in, fridge, list, check, inventory

Categories:
- fresh:      meat, vegetables, dairy, eggs, fruits, protein shakes
- frozen:     frozen meals, ice cream, frozen meat
- dry goods:  rice, noodles, oats, cereals, pasta, instant food
- drinks:     milo, oat milk, juice, beer, beverages, water
- condiments: sauces, ketchup, oyster sauce, vinegar, oil
- household:  cleaning products, toiletries, detergent
- snacks:     biscuits, chips, nuts, crackers, pretzels

Rules:
- If the message mentions multiple items, return one array element per item
- Extract brand separately from item name e.g. "Rokeby Honeycomb Protein Shake" → brand: "Rokeby", item_name: "Honeycomb Protein Shake"
- If no brand is mentioned, set brand to empty string ""
- Match brand + item_name loosely to existing fridge contents where possible
- Default expiry: 7 days from today
- Default qty: 1
- Default category: fresh
- Always return an array, even for a single action
- item_name and brand should be title cased"""


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