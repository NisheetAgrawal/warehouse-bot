import requests
import json
import os
import re
import logging

logger = logging.getLogger(__name__)

_prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
with open(_prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()

# Category words that should NEVER appear as (or inside) a brand name
_CATEGORY_WORDS = {"inverter", "solar", "panel", "cable", "wire", "structure", "mounting", "hardware"}

# If brand starts with one of these words followed by a real brand, strip the category word
# e.g. "Inverter Polycab" → "Polycab", "Solar Waaree" → "Waaree"
def _sanitize_item(item: dict) -> dict:
    """
    Post-process a single parsed item to fix common Groq mistakes:
    1. "Inverter Polycab" brand → strip "Inverter", keep "Polycab"
    2. "ACDB" or "DCDB" mixed into spec → move it to brand
    3. Manufacturer + ACDB/DCDB mixed brand → normalize to just "ACDB"/"DCDB"
    """
    brand = item.get("brand", "").strip()
    spec  = item.get("spec", "").strip()
    type_ = item.get("type", "").strip()

    brand_lower = brand.lower()

    # Fix 1: strip leading category word from brand
    # e.g. "Inverter Polycab" → "Polycab"
    for cat in _CATEGORY_WORDS:
        if brand_lower.startswith(cat + " "):
            brand = brand[len(cat):].strip()
            brand_lower = brand.lower()
            break

    # Fix 2: if brand is PURELY a category word, it probably means unknown
    # keep as-is (don't destroy it)

    # Fix 3: "Polycab ACDB" or "Waaree DCDB" → strip manufacturer, keep ACDB/DCDB
    for kw in ["acdb", "dcdb"]:
        if kw in brand_lower and brand_lower != kw:
            # Extract just the ACDB/DCDB part
            brand = kw.upper()
            brand_lower = kw
            break

    # Fix 4: spec contains "acdb"/"dcdb" → it belongs in brand, not spec
    spec_lower = spec.lower()
    for kw in ["acdb", "dcdb"]:
        if spec_lower.startswith(kw):
            # Move to brand, strip from spec
            brand = kw.upper()
            spec  = spec[len(kw):].strip(" -,")
            break

    item["brand"] = brand
    if spec is not None:
        item["spec"] = spec
    return item


def _sanitize_parsed(parsed: dict) -> dict:
    """Apply sanitization to all items in a parsed result."""
    items = parsed.get("items", [])
    if items:
        parsed["items"] = [_sanitize_item(i) for i in items]
    return parsed


def _preprocess(text: str) -> str:
    """
    Normalise common user input quirks BEFORE sending to Groq.
    This catches patterns the LLM misses (~20% of the time).
    """
    # "250PCS" / "250NOS" / "250pcs" → "250 pcs"
    text = re.sub(r'(\d+)\s*(pcs|nos|pieces|pc|units|meters|mtr|kgs?)\b',
                  lambda m: f"{m.group(1)} {m.group(2).lower()}", text, flags=re.IGNORECASE)
    # "x250" / "X250" → "250 pcs"
    text = re.sub(r'\bx(\d+)\b', r'\1 pcs', text, flags=re.IGNORECASE)
    # "AYA" / "AAYA" / "aya" at end or anywhere → normalise to "aaya"
    text = re.sub(r'\b(aya|aaya|aaaya)\b', 'aaya', text, flags=re.IGNORECASE)
    # "SE AYA" / "se aya" → "se aaya" (supplier signal)
    text = re.sub(r'\bse\s+aaya\b', 'se aaya', text, flags=re.IGNORECASE)
    return text


def parse_message(user_text: str, sender_name: str) -> dict:
    """
    Send user message to Groq Llama3-70b.
    Returns parsed intent dict or {"intent": "unknown"} on any failure.
    """
    from config import GROQ_API_KEY

    payload = {
        "model": "llama-3.3-70b-versatile",
        "temperature": 0,
        "max_tokens": 600,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{_preprocess(user_text)}\n(sent by: {sender_name})"}
        ]
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown backticks if model adds them despite instructions
        raw = raw.strip("```json").strip("```").strip()
        result = json.loads(raw)
        result = _sanitize_parsed(result)
        # If Groq returns unknown, try Python fallback before giving up
        if result.get("intent") == "unknown":
            fallback = _python_fallback(user_text)
            if fallback:
                logger.info(f"Python fallback rescued unknown intent → {fallback['intent']}")
                return fallback
        return result
    except json.JSONDecodeError as e:
        logger.error(f"Groq JSON parse error: {e} | raw: {raw}")
        return {"intent": "unknown", "message": f"Parse error"}
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"intent": "unknown", "message": f"Groq error: {str(e)}"}


# ── Structure/PVC product brand name map (for Python-level fallback) ──────────
_STRUCTURE_BRANDS = [
    "mid clamp", "end clamp", "gp leg", "gp rafter", "gp purlin",
    "gp c channel", "base plate", "earthing set", "nut bolt",
    "12x40 nut bolt", "bend", "tee", "elow", "mc4 connector",
    "25mm upvc", "flexible pipe",
]

def _python_fallback(user_text: str) -> dict | None:
    """
    Last-resort parser for simple add_stock / check_stock messages that Groq
    returns 'unknown' for. Handles "PRODUCT QTY SUPPLIER SE AYA" patterns.
    """
    text = _preprocess(user_text).lower().strip()

    # Detect add_stock signal words
    add_signals = ["aaya", "se aaya", "from ", "aya hai", "aaya hai", "aa gaya", "mila"]
    is_add = any(s in text for s in add_signals)

    # Detect check_stock signal words
    check_signals = ["kitna", "stock", "hai kitna", "kitne", "check", "batao", "bata"]
    is_check = any(s in text for s in check_signals)

    if not is_add and not is_check:
        return None

    # Try to match a known structure/PVC brand
    matched_brand = None
    for b in _STRUCTURE_BRANDS:
        if b in text:
            matched_brand = b.title()
            break
    if not matched_brand:
        return None

    if is_check:
        return {"intent": "check_stock", "items": [{"brand": matched_brand, "spec": "", "type": ""}]}

    # Extract quantity (e.g. "250 pcs", "250")
    qty_match = re.search(r'(\d+)\s*(?:pcs?|nos?|pieces?|units?)?', text)
    qty = int(qty_match.group(1)) if qty_match else 0

    # Extract party from "X se aaya" or "from X"
    party = ""
    m = re.search(r'(?:from\s+|(\w[\w\s]+?)\s+se\s+aaya)', text)
    if m:
        party = (m.group(1) or re.search(r'from\s+(\w[\w\s]+)', text).group(1) if re.search(r'from\s+(\w[\w\s]+)', text) else "").strip().title()

    logger.info(f"Python fallback matched: add_stock brand={matched_brand} qty={qty} party={party}")
    return {
        "intent": "add_stock",
        "party": party,
        "items": [{"brand": matched_brand, "spec": "", "type": "", "quantity": qty}]
    }
