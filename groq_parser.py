import requests
import json
import os
import logging

logger = logging.getLogger(__name__)

_prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
with open(_prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()


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
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Groq JSON parse error: {e} | raw: {raw}")
        return {"intent": "unknown", "message": f"Parse error"}
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"intent": "unknown", "message": f"Groq error: {str(e)}"}
