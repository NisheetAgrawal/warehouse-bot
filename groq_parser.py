import requests
import json
import os
import re
import logging
import time

logger = logging.getLogger(__name__)

_prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
with open(_prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()

_CATEGORY_WORDS = {"inverter", "solar", "panel", "cable", "wire", "structure", "mounting", "hardware"}


def _sanitize_item(item: dict) -> dict:
    brand = item.get("brand", "").strip()
    spec  = item.get("spec", "").strip()

    brand_lower = brand.lower()

    for cat in _CATEGORY_WORDS:
        if brand_lower.startswith(cat + " "):
            brand = brand[len(cat):].strip()
            brand_lower = brand.lower()
            break

    for kw in ["acdb", "dcdb"]:
        if kw in brand_lower and brand_lower != kw:
            brand = kw.upper()
            brand_lower = kw
            break

    spec_lower = spec.lower()
    for kw in ["acdb", "dcdb"]:
        if spec_lower.startswith(kw):
            brand = kw.upper()
            spec  = spec[len(kw):].strip(" -,")
            break

    item["brand"] = brand
    if spec is not None:
        item["spec"] = spec
    return item


def _sanitize_parsed(parsed: dict) -> dict:
    items = parsed.get("items", [])
    if items:
        parsed["items"] = [_sanitize_item(i) for i in items]
    return parsed


def _preprocess(text: str) -> str:
    """Normalise input before sending to Groq."""
    # "GAADI NO-CG04PR9826" → "VEHICLE CG04PR9826" (standard vehicle tag)
    text = re.sub(r'gaadi\s*no[\s\-:]+(\S+)', r'VEHICLE \1', text, flags=re.IGNORECASE)
    text = re.sub(r'vehicle\s*no[\s\-:]+(\S+)', r'VEHICLE \1', text, flags=re.IGNORECASE)
    text = re.sub(r'truck\s*no[\s\-:]+(\S+)',   r'VEHICLE \1', text, flags=re.IGNORECASE)

    # "PRODUCT-40PCS" / "PRODUCT- 250PCS" → "PRODUCT 40 pcs"
    # (dash used as separator before qty+unit, e.g. "GP LEG 4FEET-40PCS")
    text = re.sub(r'\s*-\s*(\d+)\s*(pcs|nos|pc|pieces?|mtr|meters?|kgs?|units?)\b',
                  lambda m: f" {m.group(1)} {m.group(2).lower()}", text, flags=re.IGNORECASE)
    # "- 20" at end of line (qty with no unit, e.g. "12X40 NUTBOLT- 20")
    text = re.sub(r'\s*-\s*(\d+)\s*$', r' \1', text, flags=re.MULTILINE)

    # "4FEET" / "14FEET" → "4 FEET" (number glued to dimension word)
    text = re.sub(r'(\d+)(feet|mtr|meter|kg|cm|mm)\b', r'\1 \2', text, flags=re.IGNORECASE)

    # "GPLEG" → "GP LEG", "NUTBOLT" → "NUT BOLT"
    text = re.sub(r'\bGPLEG\b', 'GP LEG', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNUTBOLT\b', 'NUT BOLT', text, flags=re.IGNORECASE)
    text = re.sub(r'\bWAARRE\b', 'Waaree', text, flags=re.IGNORECASE)
    text = re.sub(r'\bWARRE\b',  'Waaree', text, flags=re.IGNORECASE)

    # "250PCS" / "500MTR" → "250 pcs" / "500 mtr"  (no dash, just glued)
    text = re.sub(r'(\d+)\s*(pcs|nos|pieces?|pc|units?|mtr|meters?|kgs?)\b',
                  lambda m: f"{m.group(1)} {m.group(2).lower()}", text, flags=re.IGNORECASE)
    # "x250" at word boundary → "250 pcs"
    text = re.sub(r'\bx(\d+)\b', r'\1 pcs', text, flags=re.IGNORECASE)
    # Normalise "AYA" / "aya" → "aaya"
    text = re.sub(r'\b(aya|aaya|aaaya)\b', 'aaya', text, flags=re.IGNORECASE)
    return text


def _extract_qty(text: str) -> int:
    """
    Extract quantity from text, skipping product-code numbers like "12x40".
    Prefers numbers followed by unit words; falls back to largest standalone number.
    """
    # Priority: number + unit word
    m = re.search(r'\b(\d+)\s*(?:pcs|nos|pieces?|pc|units?|kg)\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Fallback: all standalone numbers NOT part of "NxM" or "Nx" product codes
    candidates = []
    for m in re.finditer(r'\b(\d+)\b', text):
        start = m.start()
        # Skip if preceded or followed by 'x' (e.g. "12x40", "x250")
        before = text[start-1:start].lower() if start > 0 else ""
        after  = text[m.end():m.end()+1].lower()
        if before in ("x",) or after in ("x",):
            continue
        candidates.append(int(m.group(1)))

    # Return the largest number found (most likely the quantity)
    return max(candidates, default=0)


def _extract_party(text: str, brand: str) -> str:
    """Extract supplier/party name from text."""
    text_clean = text.lower()
    # "DRITI ROLL SE AYA" → party = "Driti Roll"
    m = re.search(r'([\w\s]+?)\s+se\s+aaya', text_clean)
    if m:
        candidate = m.group(1).strip()
        # Don't return the product name itself as party
        if brand.lower() not in candidate:
            return candidate.title()

    # "from DRITI" / "from DRITI roll"
    m = re.search(r'\bfrom\s+([\w\s]+?)(?:\s+se\b|$|\.|,)', text_clean)
    if m:
        return m.group(1).strip().title()

    return ""


def _tok(text: str) -> set:
    """Normalize text to a set of tokens — removes spaces, dashes, punctuation."""
    text = text.lower()
    text = re.sub(r'[-_./]', ' ', text)   # dashes → spaces
    tokens = re.findall(r'[a-z0-9]+', text)
    return set(tokens)

# Aliases: what the user might write → catalog brand name tokens
_BRAND_ALIASES = {
    "gpleg":    "gp leg",
    "gp leg":   "gp leg",
    "nutbolt":  "nut bolt",
    "nut bolt": "nut bolt",
    "12x40 nut bolt": "12x40 nut bolt",
    "pvc pipe": "25mm upvc",
    "upvc":     "25mm upvc",
    "pvc":      "25mm upvc",
    "ac cable": "ac 4sx2c",
    "4sx2c":    "ac 4sx2c",
    "dc cable": "dc",
    "earthing cable": "earthing",
}

def _best_catalog_match(line_low: str, catalog: list):
    """
    Find the best catalog product for a line of text.
    Uses token overlap + spec matching to distinguish e.g. AC vs DC cable.
    Returns catalog dict or None.
    """
    line_tok = _tok(line_low)

    # Apply aliases first (handles "GPLEG" → "GP LEG" etc.)
    for alias, replacement in _BRAND_ALIASES.items():
        if _tok(alias) <= line_tok:   # alias tokens are subset of line tokens
            line_tok |= _tok(replacement)

    best_score = 0
    best_p     = None

    for p in catalog:
        # Build token set from brand + spec combined
        catalog_tok = _tok(p["brand"]) | _tok(p.get("spec", "")) | _tok(p.get("type_", ""))

        # Score = number of catalog tokens found in the line
        matches = catalog_tok & line_tok
        if not matches:
            continue

        # Require at least the main brand tokens to match
        brand_tok = _tok(p["brand"])
        brand_matches = brand_tok & line_tok
        if not brand_matches:
            continue

        # Score: brand matches weighted higher than spec matches
        score = len(brand_matches) * 3 + len(matches - brand_tok)

        if score > best_score:
            best_score = score
            best_p     = p

    return best_p if best_score >= 3 else None   # minimum 1 full brand token match


# ── Python-level fallback (uses live catalog for brand matching) ───────────────
def _python_fallback(user_text: str):
    """
    Called when Groq returns unknown or invalid JSON.
    Matches against live catalog brands to handle any product the user types.
    """
    from sheets import get_live_catalog

    text_pre  = _preprocess(user_text)
    text_low  = text_pre.lower().strip()

    # "ko gaya/ko gya/le gaya" = sold/shipped OUT — must check FIRST before add signals
    ship_signals  = ["ko gaya", "ko gya", "ko dia", "ko diya", "le gaya", "le gya",
                     "bhej diya", "bheja", "truck me", "truck mein", "challan"]
    is_ship  = any(s in text_low for s in ship_signals)

    add_signals   = ["se aaya", "se aya", "from ", "aa gaya", "aaya hai", "mila",
                     " aaya", " aya "]   # space-padded to avoid matching inside "gaya"
    check_signals = ["kitna", "stock", "hai kitna", "kitne", "batao", "bata", "check"]

    is_add   = (not is_ship) and any(s in text_low for s in add_signals)
    is_check = any(s in text_low for s in check_signals)

    # "aaya" as a standalone word (not inside gaya/bhagaya etc.)
    if not is_add and not is_ship and re.search(r'\baaya\b', text_low):
        is_add = True

    if not is_add and not is_check and not is_ship:
        return None

    catalog  = get_live_catalog()
    best_p   = _best_catalog_match(text_low, catalog)
    matched     = best_p["brand"]     if best_p else None
    matched_pid = best_p["product_id"] if best_p else ""

    if not matched and not is_ship:
        return None

    # ── Multi-line message: parse each line for its own product+qty ───────────
    lines = [l.strip() for l in user_text.strip().split('\n') if l.strip()]
    is_multiline = len(lines) > 2

    vehicle_no = "NOT PROVIDED"
    party      = ""
    items      = []

    if is_multiline:
        for line in lines:
            line_pre = _preprocess(line)
            line_low = line_pre.lower()

            # Vehicle line
            vm = re.search(r'\bVEHICLE\s+(\S+)', line_pre, re.IGNORECASE)
            if vm:
                vehicle_no = vm.group(1).upper()
                continue

            # Party line (contains "ko gaya/ko gya/le gaya")
            if any(s in line_low for s in ["ko gaya", "ko gya", "le gaya", "le gya"]):
                party = re.sub(r'\s*(ko gaya|ko gya|le gaya|le gya).*', '', line_pre,
                               flags=re.IGNORECASE).strip().title()
                continue

            # Match product from catalog using normalized token overlap
            matched_p = _best_catalog_match(line_low, catalog)
            if matched_p:
                qty = _extract_qty(line_low)
                items.append({"brand": matched_p["brand"],
                              "spec":  matched_p.get("spec",""),
                              "type":  matched_p.get("type_",""),
                              "quantity": qty,
                              "product_id": matched_p["product_id"]})

        if not items:
            return None

        if is_ship:
            logger.info(f"Multi-line fallback ship_out: {len(items)} items, party={party}, vehicle={vehicle_no}")
            return {"intent": "ship_out", "vehicle_no": vehicle_no,
                    "party": party, "operator": None, "items": items}
        logger.info(f"Multi-line fallback add_stock: {len(items)} items, party={party}")
        return {"intent": "add_stock", "party": party, "items": items}

    # ── Single-line fallback ──────────────────────────────────────────────────
    if not matched:
        return None

    qty   = _extract_qty(text_low)
    party = _extract_party(text_pre, matched)

    if is_check and not is_add and not is_ship:
        logger.info(f"Fallback check_stock: {matched} ({matched_pid})")
        return {"intent": "check_stock",
                "items": [{"brand": matched, "spec": "", "type": "", "product_id": matched_pid}]}

    if is_ship:
        logger.info(f"Fallback ship_out: {matched} ({matched_pid}) qty={qty} party={party}")
        return {"intent": "ship_out", "vehicle_no": "NOT PROVIDED", "party": party,
                "operator": None,
                "items": [{"brand": matched, "spec": "", "type": "",
                           "quantity": qty, "product_id": matched_pid}]}

    logger.info(f"Fallback add_stock: {matched} ({matched_pid}) qty={qty} party={party}")
    return {"intent": "add_stock", "party": party,
            "items": [{"brand": matched, "spec": "", "type": "",
                       "quantity": qty, "product_id": matched_pid}]}


def _is_structured_multiline(text: str) -> bool:
    """
    Detect structured truck-loading / stock-in format:
    Multiple lines each with PRODUCT-QTYPCS, ending with vehicle + party.
    These should be parsed by Python directly, not sent to Groq.
    """
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if len(lines) < 3:
        return False
    # At least 3 lines AND (last line has ko gaya/ko gya OR aaya/from)
    last = lines[-1].lower()
    return any(s in last for s in ["ko gaya", "ko gya", "le gaya", "aaya", "se aya", "from "])


def parse_message(user_text: str, sender_name: str) -> dict:
    from config import GROQ_API_KEY
    from sheets import catalog_as_prompt_text

    # ── Fast path: structured multi-line → pure Python, skip Groq entirely ───
    if _is_structured_multiline(user_text):
        result = _python_fallback(user_text)
        if result:
            logger.info(f"Structured multi-line parsed in Python: {result['intent']}, {len(result.get('items',[]))} items")
            return result

    catalog_text = catalog_as_prompt_text()
    full_prompt = (
        SYSTEM_PROMPT
        + "\n\n═══════════════════════════════════════════════════\n"
        + "LIVE PRODUCT CATALOG — match user messages to these exact product_ids:\n\n"
        + catalog_text
        + "\n\nFor EVERY item in your response include \"product_id\" from the catalog."
        + "\n═══════════════════════════════════════════════════"
    )

    payload = {
        "model": "openai/gpt-oss-120b",
        "temperature": 0,
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": f"{_preprocess(user_text)}\n(sent by: {sender_name})"}
        ]
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    raw = ""
    for attempt in range(2):   # retry once on 429
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers, json=payload, timeout=15
            )
            if resp.status_code == 429:
                logger.warning(f"Groq 429 rate limit (attempt {attempt+1})")
                if attempt == 0:
                    time.sleep(2)
                    continue
                break   # both attempts failed → go to fallback
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.strip("```json").strip("```").strip()
            result = json.loads(raw)
            result = _sanitize_parsed(result)

            if result.get("intent") == "unknown":
                fallback = _python_fallback(user_text)
                if fallback:
                    logger.info(f"Fallback rescued Groq unknown → {fallback['intent']}")
                    return fallback
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Groq JSON error: {e} | raw: {raw!r}")
            break
        except Exception as e:
            logger.error(f"Groq error: {e}")
            if attempt == 0 and "429" in str(e):
                time.sleep(2); continue
            break

    # All Groq attempts failed — use Python fallback
    fallback = _python_fallback(user_text)
    if fallback:
        logger.info(f"Fallback rescued Groq failure → {fallback['intent']}")
        return fallback
    return {"intent": "unknown", "message": "Groq unavailable"}
