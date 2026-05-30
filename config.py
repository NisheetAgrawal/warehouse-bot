import os
import json


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
GOOGLE_CREDENTIALS = json.loads(_creds_raw)
