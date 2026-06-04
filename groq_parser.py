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
            {"role": "user", "content": f"{user_text}\n(sent by: {sender_name})"}
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
        # Always run sanitization — catches Groq mistakes regardless of prompt
        return _sanitize_parsed(result)
    except json.JSONDecodeError as e:
        logger.error(f"Groq JSON parse error: {e} | raw: {raw}")
        return {"intent": "unknown", "message": f"Parse error"}
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"intent": "unknown", "message": f"Groq error: {str(e)}"}
