from datetime import datetime
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from ai import parse_intent
from database import get_all_items, get_item, upsert_item, soft_delete_item, get_expiring_items, get_out_of_stock_items
from config import EXPIRY_WARNING_DAYS

HELP_TEXT = (
    "I didn't quite get that. Try:\n"
    "• <i>bought 2 Rokeby protein shakes expiring end of May</i>\n"
    "• <i>drank the last oat milk</i>\n"
    "• <i>threw out the cheese</i>\n"
    "• <i>what's in the fridge</i>"
)

CATEGORY_HEADERS = {
    "fresh":      "🥩 FRESH",
    "frozen":     "🧊 FROZEN",
    "dry goods":  "🥫 DRY GOODS",
    "drinks":     "🍺 DRINKS",
    "condiments": "🫙 CONDIMENTS",
    "household":  "🧴 HOUSEHOLD",
    "snacks":     "🥨 SNACKS",
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
    "/expiring — items expiring within 7 days\n"
    "/restock — items that are out of stock\n"
    "/intro — show this message"
)


def expiry_emoji(days_left: int) -> str:
    if days_left <= 0:
        return "💀"
    if days_left <= 7:
        return "☢️"
    if days_left <= 30:
        return "⚠️"
    return "✅"


def display_name(row) -> str:
    """Returns 'Brand Item Name' or just 'Item Name' if no brand."""
    if row["brand"]:
        return f"{row['brand']} {row['item_name']}"
    return row["item_name"]


def format_item_line(row, today) -> str:
    days_left  = (row["expiry"] - today).days
    emoji      = expiry_emoji(days_left)
    expiry_str = row["expiry"].strftime("%d %b")

    if days_left <= 0:
        timing = "expired!"
    elif days_left == 1:
        timing = "1d left"
    else:
        timing = f"{days_left}d left"

    return f"{emoji} {row['qty']}x {display_name(row)} — {expiry_str} ({timing})"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_intro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO_TEXT, parse_mode="HTML")


async def cmd_fridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_view(update, get_all_items())


async def cmd_expiring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = get_expiring_items(days=7)
    if not items:
        await update.message.reply_text("Nothing expiring in the next 7 days. 🎉")
        return
    today = datetime.now().date()
    lines = [format_item_line(r, today) for r in items]
    await update.message.reply_text(
        "<b>☢️ Expiring within 7 days</b>\n" + "\n".join(lines),
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


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

async def handle_add(update: Update, parsed: dict):
    brand     = parsed.get("brand") or ""
    item_name = parsed["item_name"]
    qty       = int(parsed.get("qty", 1))
    category  = parsed.get("category", "fresh").lower()
    expiry    = datetime.strptime(parsed["expiry"], "%Y-%m-%d").date()

    existing = get_item(brand, item_name)
    action   = "updated" if existing and existing["qty"] > 0 else "added"
    upsert_item(brand, item_name, expiry, qty, category)

    days_left   = (expiry - datetime.now().date()).days
    expiry_warn = f"\n⚠️ Heads up — expires in {days_left}d!" if days_left <= 7 else ""
    header      = CATEGORY_HEADERS.get(category, "📦 OTHER")
    name        = f"{brand} {item_name}".strip()

    await update.message.reply_text(
        f"✅ <b>{name}</b> {action}\n"
        f"{header} | Qty: {qty} | Expiry: {expiry.strftime('%d %b %y')}{expiry_warn}",
        parse_mode="HTML"
    )


async def handle_consume(update: Update, parsed: dict):
    brand          = parsed.get("brand") or ""
    item_name      = parsed["item_name"]
    qty_to_consume = int(parsed.get("qty", 1))
    row            = get_item(brand, item_name)
    name           = f"{brand} {item_name}".strip()

    if not row or row["qty"] == 0:
        await update.message.reply_text(
            f"I don't see <b>{name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    new_qty = row["qty"] - qty_to_consume
    if new_qty <= 0:
        soft_delete_item(brand, item_name)
        await update.message.reply_text(
            f"All done! <b>{name}</b> is out of stock. 🏁", parse_mode="HTML"
        )
    else:
        upsert_item(brand, item_name, row["expiry"], new_qty, row["category"])
        await update.message.reply_text(
            f"Got it! Used {qty_to_consume}x <b>{name}</b>. {new_qty} remaining. 👍",
            parse_mode="HTML"
        )


async def handle_throw(update: Update, parsed: dict):
    brand     = parsed.get("brand") or ""
    item_name = parsed["item_name"]
    row       = get_item(brand, item_name)
    name      = f"{brand} {item_name}".strip()

    if not row or row["qty"] == 0:
        await update.message.reply_text(
            f"I don't see <b>{name}</b> in the fridge.", parse_mode="HTML"
        )
        return

    soft_delete_item(brand, item_name)
    await update.message.reply_text(
        f"🗑 <b>{name}</b> thrown away. What a waste!", parse_mode="HTML"
    )


async def handle_view(update: Update, fridge: list):
    if not fridge:
        await update.message.reply_text("The fridge is bare! 🏜️ Time to restock.")
        return

    today       = datetime.now().date()
    by_category = {}

    for row in fridge:
        cat = row["category"].lower()
        by_category.setdefault(cat, []).append(row)

    parts = []
    for cat, items in sorted(by_category.items()):
        header = CATEGORY_HEADERS.get(cat, "📦 OTHER")
        lines  = [format_item_line(r, today) for r in items]
        parts.append(f"<b>{header}</b>\n" + "\n".join(lines))

    await update.message.reply_text("\n\n".join(parts), parse_mode="HTML")


# ---------------------------------------------------------------------------
# Main entry point for all messages
# ---------------------------------------------------------------------------

INTENT_HANDLERS = {
    "add":     handle_add,
    "consume": handle_consume,
    "throw":   handle_throw,
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text   = update.message.text
    fridge = get_all_items()

    try:
        actions = parse_intent(text, fridge)

        for parsed in actions:
            intent = parsed.get("intent")

            if intent == "view":
                await handle_view(update, fridge)
            elif intent in INTENT_HANDLERS:
                await INTENT_HANDLERS[intent](update, parsed)
            else:
                await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

    except Exception as e:
        print(f"Error handling message: {e}")
        await update.message.reply_text("Something went wrong, please try again.")