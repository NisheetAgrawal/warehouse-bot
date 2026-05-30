import os
import json
import logging

logger = logging.getLogger(__name__)


def _require(key):
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


TELEGRAM_TOKEN = _require("TELEGRAM_TOKEN")
GROQ_API_KEY = _require("GROQ_API_KEY")
GOOGLE_SHEET_ID = _require("GOOGLE_SHEET_ID")

# Google credentials stored as full JSON string in env var
_creds_raw = _require("GOOGLE_CREDENTIALS_JSON")

# Fix: Render sometimes escapes the private_key newlines as literal \\n
# We restore them so json.loads works correctly
_creds_raw = _creds_raw.replace("\\\\n", "\\n")

try:
    GOOGLE_CREDENTIALS = json.loads(_creds_raw)
except json.JSONDecodeError as e:
    raise EnvironmentError(
        f"GOOGLE_CREDENTIALS_JSON is not valid JSON: {e}\n"
        f"First 200 chars: {_creds_raw[:200]}"
    )
