from datetime import datetime
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from ai import parse_intent
from database import (
    get_all_items, get_item, get_item_fuzzy, upsert_item,
    soft_delete_item, get_expiring_items, get_out_of_stock_items
)

HELP_TEXT = (
    "I didn't quite get that. Try:\n"
    "• <i>bought 2 Rokeby protein shakes expiring end of May</i>\n"
    "• <i>drank the last oat milk</i>\n"
    "• <i>threw out the cheese</i>\n"
    "• <i>what's in the fridge</i>"
)

CATEGORY_HEADERS = {
    "fresh":      "🥩 FRESH",
    "herbs":      "🌿 HERBS",
    "leftovers":  "🍱 LEFTOVERS",
    "frozen":     "🧊 FROZEN",
    "dry goods":  "🥫 DRY GOODS",
    "drinks":     "🍺 DRINKS",
    "condiments": "🫙 CONDIMENTS",
    "household":  "🧴 HOUSEHOLD",
    "snacks":     "🥨 SNACKS",
}

# Default expiry days per category — used for 20% warning threshold
CATEGORY_DEFAULT_DAYS = {
    "fresh":      14,
    "herbs":      21,
    "leftovers":  7,
    "frozen":     90,
    "dry goods":  180,
    "drinks":     90,
    "condiments": 180,
    "household":  360,
    "snacks":     60,
}

INTRO_TEXT = (
    "<b>👋 Hey! I'm ErrandElf — your fridge assistant.</b>\n\n"
    "Just talk to me naturally:\n\n"
    "➕ <b>Add items</b>\n"
    "<i>bought 2 Rokeby protein shakes expiring end of May</i>\n\n"
    "✅ <b>Consume items</b>\n"
    "<i>drank an oat milk</i>\n\n"
    "🗑 <b>Throw items</b>\n"
    "<i>threw out the leftover pasta</i>\n\n"
    "📦 <b>Check your fridge</b>\n"
    "<i>what's in the fridge</i>\n\n"
    "<b>Quick commands:</b>\n"
    "/fridge — view all inventory\n"
    "/expiring — items expiring soon\n"
    "/restock — items that are out of stock\n"
    "/categories — view all categories\n"
    "/intro — show this message"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def display_name(row) -> str:
    if row["brand"]:
        return f"{row['brand']} {row['item_name']}"
    return row["item_name"]


def expiry_emoji(days_left: int, category: str) -> str:
    default_days = CATEGORY_DEFAULT_DAYS.get(category.lower(), 14)
    warning_threshold = default_days * 0.2

    if days_left <= 0:
        return "💀"
    if days_left <= warning_threshold:
        return "☢️"
    return "✅"


def format_item_line(row, today) -> str:
    days_left = (row["expiry"] - today).days
    emoji     = expiry_emoji(days_left, row["category"])

    if days_left <= 0:
        timing = " — expired!"
    elif days_left == 1:
        timing = " — 1d left"
    else:
        timing = f" — {days_left}d left"

    return f"{emoji} {row['qty']}x {display_name(row)}{timing}"


def resolve_item(brand: str, item_name: str):
    """Try exact match first, fall back to fuzzy search."""
    row = get_item(brand, item_name)
    if row and row["qty"] > 0:
        return row
    return get_item_fuzzy(item_name)


# ---------------------------------------------------------------------------
# Command handlers (no AI credits used)
# ---------------------------------------------------------------------------

async def cmd_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO_TEXT, parse_mode="HTML")


async def cmd_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_view(update, get_all_items())


async def cmd_expiring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().date()
    items = get_all_items()

    # Filter by 20% threshold per category
    expiring = []
    for row in items:
        days_left = (row["expiry"] - today).days
        default_days = CATEGORY_DEFAULT_DAYS.get(row["category"].lower(), 14)
        if days_left <= default_days * 0.2:
            expiring.append(row)

    if not expiring:
        await update.message.reply_text("Nothing expiring soon. You're all good! 🎉")
        return

    lines = [format_item_line(r, today) for r in expiring]
    await update.message.reply_text(
        "<b>☢️ Expiring soon</b>\n" + "\n".join(lines),
        parse_mode="HTML"
    )


async def cmd_restock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = get_out_of_stock_items()
    if not items:
        await update.message.reply_text("Nothing out of stock. You're well stocked! 💪")
        return
    lines = [f"• {display_name(r)}" for r in items]
    await update.message.reply_text(
        "<b>🛒 Out of stock — time to restock</b>\n" + "\n".join(lines),
        parse_mode="HTML"
    )


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"{emoji}  {cat.upper()} — {CATEGORY_DEFAULT_DAYS[cat]}d default"
             for cat, emoji in {
                "fresh":      "🥩",
                "herbs":      "🌿",
                "leftovers":  "🍱",
                "frozen":     "🧊",
                "dry goods":  "🥫",
                "drinks":     "🍺",
                "condiments": "🫙",
                "household":  "🧴",
                "snacks":     "🥨",
             }.items()]
    await update.message.reply_text(
        "<b>📋 Categories</b>\n" + "\n".join(lines),
        parse_mode="HTML"
    )


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

async def handle_add(update: Update, parsed_list: list):
    """Handles one or more add actions, grouped into a single reply."""
    today      = datetime.now().date()
    added      = []
    by_category = defaultdict(list)

    for parsed in parsed_list:
        brand     = parsed.get("brand") or ""
        item_name = parsed["item_name"]
        qty       = int(parsed.get("qty", 1))
        category  = parsed.get("category", "fresh").lower()
        expiry    = datetime.strptime(parsed["expiry"], "%Y-%m-%d").date()

        existing = get_item(brand, item_name)
        upsert_item(brand, item_name, expiry, qty, category)

        name = f"{brand} {item_name}".strip()
        by_category[category].append(f"{qty}x {name}")
        added.append(name)

    if len(added) == 1:
        # Single item — concise reply
        p        = parsed_list[0]
        brand    = p.get("brand") or ""
        category = p.get("category", "fresh").lower()
        header   = CATEGORY_HEADERS.get(category, "📦 OTHER")
        name     = f"{brand} {p['item_name']}".strip()
        existing = get_item(brand, p["item_name"])
        action   = "updated" if existing else "added"

        await update.message.reply_text(
            f"✅ <b>{name}</b> {action}\n{header} | Qty: {p.get('qty', 1)}",
            parse_mode="HTML"
        )
    else:
        # Multiple items — grouped by category
        parts = [f"✅ <b>{len(added)} items added</b>"]
        for cat, names in sorted(by_category.items()):
            header = CATEGORY_HEADERS.get(cat, "📦 OTHER")
            parts.append(f"\n<b>{header}</b>\n" + "\n".join(names))
        await update.message.reply_text("\n".join(parts), parse_mode="HTML")


async def handle_consume(update: Update, parsed: dict):
    brand          = parsed.get("brand") or ""
    item_name      = parsed["item_name"]
    qty_to_consume = int(parsed.get("qty", 1))
    row            = resolve_item(brand, item_name)
    name           = f"{brand} {item_name}".strip()

    if not row:
        await update.message.reply_text(
            f"I don't see <b>{name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    # Use resolved row's brand/item_name for DB ops
    actual_brand = row["brand"]
    actual_name  = row["item_name"]
    display      = display_name(row)
    new_qty      = row["qty"] - qty_to_consume

    if new_qty <= 0:
        soft_delete_item(actual_brand, actual_name)
        await update.message.reply_text(
            f"All done! <b>{display}</b> is out of stock. 🏁", parse_mode="HTML"
        )
    else:
        upsert_item(actual_brand, actual_name, row["expiry"], new_qty, row["category"])
        await update.message.reply_text(
            f"Got it! Used {qty_to_consume}x <b>{display}</b>. {new_qty} remaining. 👍",
            parse_mode="HTML"
        )


async def handle_throw(update: Update, parsed: dict):
    brand     = parsed.get("brand") or ""
    item_name = parsed["item_name"]
    row       = resolve_item(brand, item_name)
    name      = f"{brand} {item_name}".strip()

    if not row:
        await update.message.reply_text(
            f"I don't see <b>{name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    soft_delete_item(row["brand"], row["item_name"])
    await update.message.reply_text(
        f"🗑 <b>{display_name(row)}</b> thrown away. What a waste!", parse_mode="HTML"
    )


async def handle_view(update: Update, fridge: list):
    if not fridge:
        await update.message.reply_text("The fridge is bare! 🏜️ Time to restock.")
        return

    today       = datetime.now().date()
    by_category = defaultdict(list)

    for row in fridge:
        by_category[row["category"].lower()].append(row)

    parts = []
    for cat in CATEGORY_HEADERS:
        if cat not in by_category:
            continue
        header = CATEGORY_HEADERS[cat]
        lines  = [format_item_line(r, today) for r in by_category[cat]]
        parts.append(f"<b>{header}</b>\n" + "\n".join(lines))

    await update.message.reply_text("\n\n".join(parts), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text   = update.message.text
    fridge = get_all_items()

    try:
        actions = parse_intent(text, fridge)

        # Batch all add intents into a single grouped reply
        adds   = [a for a in actions if a.get("intent") == "add"]
        others = [a for a in actions if a.get("intent") != "add"]

        if adds:
            await handle_add(update, adds)

        for parsed in others:
            intent = parsed.get("intent")
            if intent == "view":
                await handle_view(update, fridge)
            elif intent == "consume":
                await handle_consume(update, parsed)
            elif intent == "throw":
                await handle_throw(update, parsed)
            else:
                await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

    except Exception as e:
        print(f"Error handling message: {e}")
        await update.message.reply_text("Something went wrong, please try again.")