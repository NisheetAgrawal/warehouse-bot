import logging
import io
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from dotenv import load_dotenv
load_dotenv()

# Render requires a port to be open — run a minimal health server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Warehouse bot is running")
    def log_message(self, *args):
        pass  # silence access logs

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.getLogger(__name__).info(f"Health server on port {port}")

from config import TELEGRAM_TOKEN
from groq_parser import parse_message
from sheets import get_stock, add_stock, deduct_stock, add_new_product, update_rate, _normalize, search_similar_products
from pdf_generator import generate_delivery_receipt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ── /start ───────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏭 *GURUKRIPA ENTERPRISES — Warehouse Bot*\n\n"
        "📦 *Stock check:*\n`kitna hai Waaree 575 DCR`\n\n"
        "➕ *Maal aaya (supplier ke saath):*\n`aaya 100 Waaree 575 DCR - Raj Traders se`\n\n"
        "🚛 *Truck loading (buyer ke saath):*\n`truck HR55AB1234: Waaree 575 DCR x20 - Shyam Solar ko`\n\n"
        "💰 *Rate update:*\n`Waaree 605 ka rate 18500 krdo`\n\n"
        "🆕 *Naya product add karo:*\n`naya product: Waaree, 650, DCR, Solar Panel`\n"
        "_(Categories: Solar Panel / Inverter / Cable / ACDB/DCDB)_\n\n"
        "✏️ *Challan edit:* Delivery ke baad PDF ke neeche Edit button aata hai",
        parse_mode="Markdown"
    )


# ── Main message handler ─────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    sender    = update.message.from_user.first_name or "Unknown"
    chat_id   = update.message.chat_id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Edit mode — user is correcting a previous challan
    if context.chat_data.get("awaiting_edit"):
        await handle_edit_input(update, context, sender, chat_id)
        return

    parsed = parse_message(user_text, sender)
    intent = parsed.get("intent", "unknown")
    logger.info(f"User={sender} | Intent={intent} | Text={user_text[:60]}")

    if intent == "check_stock":
        await _handle_check_stock(update, parsed, context)

    elif intent == "add_stock":
        await _handle_add_stock(update, parsed, sender, context)

    elif intent == "ship_out":
        await _handle_ship_out(update, context, parsed, sender, chat_id)

    elif intent == "add_product":
        await _handle_add_product(update, parsed, sender)

    elif intent == "update_rate":
        await _handle_update_rate(update, parsed)

    else:
        await update.message.reply_text(
            "🙏 Samajh nahi aaya bhai.\n\n"
            "Aise bhejo:\n"
            "• `kitna hai Waaree 575 DCR`\n"
            "• `aaya 50 Adani 540 DCR`\n"
            "• `truck HR55AB1234: Waaree 575 x10`\n\n"
            "• `/start` — poora guide dekho",
            parse_mode="Markdown"
        )


# ── Check stock ──────────────────────────────────────────────────
async def _handle_check_stock(update, parsed, context):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text("Kaunsa product? Dobara bhejo.")
        return

    lines = []
    for item in items:
        info = get_stock(item["brand"], item["spec"], item.get("type", "DCR"))
        if not info["found"]:
            await _suggest_products(update, context, item, {"intent": "check_stock"})
            continue
        qty  = info["quantity"]
        rate = info["rate"]
        if qty == 0:
            status = "❌ Out of Stock"
        elif qty < 5:
            status = "⚠️ Low Stock"
        else:
            status = "✅ In Stock"
        rate_str = f"₹{rate}" if rate and str(rate).strip() not in ("0", "", "N/A") else "Rate set nahi"
        lines.append(
            f"*{info['brand']} {info['spec']} {info['type']}*\n"
            f"Stock: *{qty} units* {status}\n"
            f"Rate: {rate_str}"
        )
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


# ── Add stock ────────────────────────────────────────────────────
async def _handle_add_stock(update, parsed, sender, context):
    items = parsed.get("items", [])
    party = parsed.get("party", "")
    if not items:
        await update.message.reply_text("Kitna add karna hai? Dobara bhejo.")
        return

    lines = []
    for item in items:
        qty = item.get("quantity", 0)
        if not qty or int(qty) <= 0:
            lines.append(f"❌ Quantity missing: {item['brand']} {item['spec']}")
            continue
        result = add_stock(
            item["brand"], item["spec"], item.get("type", "DCR"),
            int(qty), sender, party
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*\n"
                f"{result['before']} → *{result['after']}* (+{result['quantity']})"
            )
        elif "Nahi mila" in result.get("error", ""):
            await _suggest_products(update, context, item,
                {"intent": "add_stock", "sender": sender, "party": party, **item})
        else:
            lines.append(f"❌ {result['error']}")

    party_line = f"\n🏪 Supplier: *{party}*" if party else ""
    await update.message.reply_text(
        f"📦 *Stock Updated:*{party_line}\n\n" + "\n\n".join(lines),
        parse_mode="Markdown"
    )


# ── Ship out ─────────────────────────────────────────────────────
async def _handle_ship_out(update, context, parsed, sender, chat_id):
    items      = parsed.get("items", [])
    vehicle_no = parsed.get("vehicle_no") or "NOT PROVIDED"
    party      = parsed.get("party", "")

    if not items:
        await update.message.reply_text("Kaunsa maal ja raha hai? Dobara bhejo.")
        return

    await update.message.reply_text(
        f"🚛 Processing shipment for vehicle *{vehicle_no}*...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")

    results = []
    errors  = []

    for item in items:
        qty = item.get("quantity", 0)
        if not qty or int(qty) <= 0:
            errors.append(f"Quantity missing for {item['brand']} {item['spec']}")
            continue
        result = deduct_stock(
            item["brand"], item["spec"], item.get("type", "DCR"),
            int(qty), vehicle_no, sender, party
        )
        if result["success"]:
            results.append(result)
        elif "Nahi mila" in result.get("error", ""):
            await _suggest_products(update, context, item,
                {"intent": "ship_out", "sender": sender, "party": party,
                 "vehicle_no": vehicle_no, **item})
        else:
            errors.append(result.get("error", "Unknown error"))

    if not results and errors:
        await update.message.reply_text(
            "❌ *Shipment fail ho gaya:*\n\n" + "\n".join(errors),
            parse_mode="Markdown"
        )
        return

    pdf_items = [
        {"brand": r["brand"], "spec": r["spec"], "type": r["type"], "quantity": r["quantity"]}
        for r in results
    ]

    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    pdf_bytes = generate_delivery_receipt(vehicle_no, sender, pdf_items, party)
    pdf_io    = io.BytesIO(pdf_bytes)
    pdf_name  = f"challan_{vehicle_no}_{datetime.now(IST).strftime('%d%b%Y_%H%M')}.pdf"

    total_qty = sum(r["quantity"] for r in results)

    summary_lines = [
        f"✅ *{r['brand']} {r['spec']} {r['type']}*: -{r['quantity']} units"
        for r in results
    ]
    if errors:
        summary_lines.append("\n⚠️ *Skipped:*")
        summary_lines.extend([f"• {e}" for e in errors])

    party_line = f"\n🏪 Party: *{party}*" if party else ""
    caption = (
        f"🚛 *Delivery Challan*\n"
        f"Vehicle: *{vehicle_no}*{party_line}\n"
        f"Total: *{total_qty} units*\n\n"
        + "\n".join(summary_lines)
    )

    # Store last shipment for edit functionality
    context.chat_data["last_shipment"] = {
        "vehicle_no": vehicle_no,
        "sender": sender,
        "party": party,
        "items": [
            {"brand": r["brand"], "spec": r["spec"], "type": r["type"], "quantity": r["quantity"]}
            for r in results
        ]
    }

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit Challan", callback_data="edit_challan")
    ]])

    await context.bot.send_document(
        chat_id=chat_id,
        document=pdf_io,
        filename=pdf_name,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ── Add new product ──────────────────────────────────────────────
async def _handle_add_product(update, parsed, sender):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text(
            "Product ki details do.\nFormat: `naya product: Solar Panel, Waaree, 650W, DCR`",
            parse_mode="Markdown"
        )
        return

    lines = []
    for item in items:
        result = add_new_product(
            item.get("category", ""),
            item["brand"],
            item["spec"],
            item.get("type", "DCR"),
            sender
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}* add ho gaya!\n"
                f"Quantity abhi 0 hai — jab maal aaye tab update karo."
            )
        else:
            lines.append(f"❌ {result.get('error', 'Error')}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


# ── Product suggestion helpers ───────────────────────────────────
import json as _json

async def _suggest_products(update, context, failed_item: dict, action_context: dict):
    """Show 'Did you mean?' buttons when product not found."""
    suggestions = search_similar_products(
        failed_item["brand"], failed_item["spec"], failed_item.get("type", "DCR")
    )
    if not suggestions:
        await update.message.reply_text(
            f"❌ *{failed_item['brand']} {failed_item['spec']}* sheet mein nahi mila.\n"
            "Pehle `naya product` se add karo.",
            parse_mode="Markdown"
        )
        return

    # Store pending action so callback can execute it
    context.chat_data["pending_action"] = {
        "action_context": action_context,   # intent, vehicle_no, party, sender, other items
        "failed_item":    failed_item,
    }

    buttons = []
    for i, s in enumerate(suggestions):
        label = f"{s['brand']} {s['spec']} {s['type']} (stock: {s['quantity']})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pick_{i}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="pick_cancel")])

    context.chat_data["suggestions"] = suggestions
    await update.message.reply_text(
        f"❓ *'{failed_item['brand']} {failed_item['spec']}'* exactly nahi mila.\n\n"
        "Kya in mein se koi hai?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def product_pick_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "pick_cancel":
        context.chat_data.pop("pending_action", None)
        context.chat_data.pop("suggestions", None)
        await query.message.reply_text("❌ Cancelled.")
        return

    idx = int(data.split("_")[1])
    suggestions   = context.chat_data.get("suggestions", [])
    pending       = context.chat_data.get("pending_action", {})
    action_ctx    = pending.get("action_context", {})
    failed_item   = pending.get("failed_item", {})

    if idx >= len(suggestions):
        await query.message.reply_text("❌ Invalid selection.")
        return

    chosen = suggestions[idx]
    # Replace failed item fields with chosen product
    corrected_item = {**failed_item, "brand": chosen["brand"], "spec": chosen["spec"], "type": chosen["type"]}

    intent   = action_ctx.get("intent")
    sender   = action_ctx.get("sender", "Unknown")
    party    = action_ctx.get("party", "")
    chat_id  = query.message.chat_id

    if intent == "check_stock":
        info = get_stock(chosen["brand"], chosen["spec"], chosen["type"])
        qty  = info["quantity"]
        rate = info.get("rate", "")
        status = "✅ In Stock" if qty >= 5 else ("⚠️ Low Stock" if qty > 0 else "❌ Out of Stock")
        rate_str = f"₹{rate}" if rate and str(rate).strip() not in ("0", "", "N/A") else "Rate set nahi"
        await query.message.reply_text(
            f"*{chosen['brand']} {chosen['spec']} {chosen['type']}*\n"
            f"Stock: *{qty} units* {status}\nRate: {rate_str}",
            parse_mode="Markdown"
        )

    elif intent == "add_stock":
        qty = int(corrected_item.get("quantity", 0))
        result = add_stock(chosen["brand"], chosen["spec"], chosen["type"], qty, sender, party)
        if result["success"]:
            await query.message.reply_text(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*\n"
                f"{result['before']} → *{result['after']}* (+{qty})",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(f"❌ {result['error']}")

    elif intent == "ship_out":
        qty        = int(corrected_item.get("quantity", 0))
        vehicle_no = action_ctx.get("vehicle_no", "NOT PROVIDED")
        result = deduct_stock(chosen["brand"], chosen["spec"], chosen["type"], qty, vehicle_no, sender, party)
        if result["success"]:
            await query.message.reply_text(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*: -{qty} units\n"
                f"Stock: {result['before']} → *{result['after']}*",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(f"❌ {result['error']}")

    context.chat_data.pop("pending_action", None)
    context.chat_data.pop("suggestions", None)


# ── Edit challan callback ────────────────────────────────────────
async def edit_challan_callback(update, context):
    query = update.callback_query
    await query.answer()

    last = context.chat_data.get("last_shipment")
    if not last:
        await query.message.reply_text("❌ Koi recent challan nahi mila edit karne ke liye.")
        return

    lines = [f"• {i['brand']} {i['spec']} {i['type']} x{i['quantity']}" for i in last["items"]]
    context.chat_data["awaiting_edit"] = True

    await query.message.reply_text(
        "✏️ *Challan Edit Mode*\n\n"
        "Current items:\n" + "\n".join(lines) + "\n\n"
        "Corrected quantities bhejo — ek line per item:\n"
        "`Waaree 575 DCR x18`\n"
        "`Polycab 5kw 3P x3`\n\n"
        "Sirf woh items bhejo jo change karne hain.",
        parse_mode="Markdown"
    )


def _parse_correction_line(line: str):
    """
    Parse 'Waaree 575 DCR x18' or 'Citizen 550 DCR X10' directly — no Groq needed.
    Returns dict with brand/spec/type/quantity or None.
    """
    import re
    line = line.strip().lstrip("•-").strip()
    qty_match = re.search(r'[xX×]\s*(\d+)', line)
    if not qty_match:
        # Try trailing number: "Citizen 550 DCR 10"
        qty_match = re.search(r'\s(\d+)\s*$', line)
    if not qty_match:
        return None
    qty = int(qty_match.group(1))
    rest = line[:qty_match.start()].strip()
    parts = rest.split()
    if not parts:
        return None
    type_ = "DCR"
    if parts and parts[-1].upper() in ("DCR", "N-DCR", "NDCR", "1P", "3P"):
        type_ = parts.pop()
    brand = parts[0] if parts else ""
    spec  = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {"brand": brand, "spec": spec, "type": type_, "quantity": qty}


async def handle_edit_input(update, context, sender, chat_id):
    """Process correction lines like 'Waaree 575 DCR x18'"""
    last = context.chat_data.get("last_shipment", {})
    text = update.message.text.strip()
    context.chat_data["awaiting_edit"] = False

    corrections = []
    for line in text.splitlines():
        c = _parse_correction_line(line)
        if c:
            corrections.append(c)

    if not corrections:
        await update.message.reply_text(
            "❌ Format samajh nahi aaya.\nExample: `Citizen 550 DCR x10`",
            parse_mode="Markdown"
        )
        return

    results = []
    errors  = []

    for corr in corrections:
        new_qty = int(corr.get("quantity", 0))
        if new_qty <= 0:
            errors.append(f"Quantity missing: {corr['brand']} {corr['spec']}")
            continue

        # Find original item to calculate diff
        orig_qty = 0
        for orig in last.get("items", []):
            if (_normalize(orig["brand"]) in _normalize(corr["brand"]) or
                    _normalize(corr["brand"]) in _normalize(orig["brand"])):
                orig_qty = orig["quantity"]
                break

        diff = new_qty - orig_qty  # positive = need to add back more, negative = deduct more
        brand, spec, type_ = corr["brand"], corr["spec"], corr.get("type", "DCR")

        if diff > 0:
            # Shipped too few originally — deduct the extra difference
            result = deduct_stock(brand, spec, type_, diff, last["vehicle_no"], sender, last.get("party", ""))
        elif diff < 0:
            # Shipped too many originally — add back the excess
            result = add_stock(brand, spec, type_, abs(diff), sender, last.get("party", ""))
        else:
            results.append({"brand": brand, "spec": spec, "type": type_, "quantity": new_qty, "rate": 0})
            continue

        if result["success"]:
            results.append({"brand": brand, "spec": spec, "type": type_, "quantity": new_qty, "rate": 0})
        else:
            errors.append(result.get("error", "Unknown error"))

    # Update last_shipment with corrected quantities
    for corr in corrections:
        for orig in context.chat_data["last_shipment"]["items"]:
            if _normalize(orig["brand"]) in _normalize(corr["brand"]) or _normalize(corr["brand"]) in _normalize(orig["brand"]):
                orig["quantity"] = int(corr.get("quantity", orig["quantity"]))

    if not results and errors:
        await update.message.reply_text("❌ Edit fail:\n" + "\n".join(errors), parse_mode="Markdown")
        return

    # Regenerate PDF with all corrected items
    all_items = context.chat_data["last_shipment"]["items"]
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    pdf_bytes = generate_delivery_receipt(last["vehicle_no"], sender, all_items, last.get("party", ""))
    pdf_io    = io.BytesIO(pdf_bytes)
    pdf_name  = f"challan_EDITED_{last['vehicle_no']}_{datetime.now(IST).strftime('%d%b%Y_%H%M')}.pdf"

    lines = [f"✅ *{i['brand']} {i['spec']} {i['type']}*: {i['quantity']} units" for i in all_items]
    if errors:
        lines.append("\n⚠️ Skipped:\n" + "\n".join(errors))

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit Challan", callback_data="edit_challan")]])

    await context.bot.send_document(
        chat_id=chat_id,
        document=pdf_io,
        filename=pdf_name,
        caption="✏️ *Edited Challan*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ── Update rate ──────────────────────────────────────────────────
async def _handle_update_rate(update, parsed):
    items = parsed.get("items", [])
    if not items:
        await update.message.reply_text("Kaunsa product aur kitna rate? Dobara bhejo.")
        return

    lines = []
    for item in items:
        rate = item.get("rate", 0)
        if not rate or int(rate) <= 0:
            lines.append(f"❌ Rate missing: {item['brand']} {item['spec']}")
            continue
        result = update_rate(
            item["brand"], item["spec"], item.get("type", "DCR"), int(rate)
        )
        if result["success"]:
            lines.append(
                f"✅ *{result['brand']} {result['spec']} {result['type']}*\n"
                f"Rate: *₹{int(rate):,}* per unit\n"
                f"Total ({result['quantity']} units): *₹{result['quantity'] * int(rate):,}*"
            )
        else:
            lines.append(f"❌ {result['error']}")

    await update.message.reply_text(
        "💰 *Rate Updated:*\n\n" + "\n\n".join(lines),
        parse_mode="Markdown"
    )


# ── Error handler ────────────────────────────────────────────────
async def error_handler(update, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text(
            "⚠️ Kuch gadbad ho gayi. Thodi der mein dobara try karo."
        )


# ── Entry point ──────────────────────────────────────────────────
def main():
    import asyncio
    # Python 3.10+ no longer auto-creates an event loop — set one explicitly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    start_health_server()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(edit_challan_callback, pattern="^edit_challan$"))
    app.add_handler(CallbackQueryHandler(product_pick_callback, pattern="^pick_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    logger.info("Warehouse bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
