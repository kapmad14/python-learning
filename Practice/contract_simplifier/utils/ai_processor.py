# utils/ai_processor.py
import os
import streamlit as st
import openai
import logging

logger = logging.getLogger(__name__)

# --- API key setup: Streamlit secrets preferred, else env var ---
OPENAI_KEY = None
if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
    OPENAI_KEY = st.secrets["OPENAI_API_KEY"]
else:
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_KEY:
    # We don't raise at import time; callers will see authentication errors when they try to use the API.
    logger.warning("OPENAI_API_KEY not found in Streamlit secrets or environment variables.")
else:
    # set legacy openai.api_key (helps older client usage)
    try:
        openai.api_key = OPENAI_KEY
    except Exception:
        # ignore if openai doesn't expose api_key as attribute in this installed package variant
        pass

# --- Helper: choose token budget by length ---
LENGTH_TO_MAX_TOKENS = {
    "short": 300,
    "medium": 800,
    "detailed": 1400,
}

def _call_openai_chat(messages, model="gpt-3.5-turbo", max_tokens=800, temperature=0.5):
    """
    Call OpenAI chat completion, trying the newer OpenAI client first (openai>=1.0.0),
    then falling back to the older openai.ChatCompletion API if the newer client isn't available.
    Returns the assistant text (string) or raises a RuntimeError on failure.
    """
    # Try modern client (openai>=1.0)
    try:
        from openai import OpenAI as OpenAIClient
        client = OpenAIClient(api_key=OPENAI_KEY) if OPENAI_KEY else OpenAIClient()
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # modern client: resp.choices[0].message.content
        try:
            return resp.choices[0].message.content.strip()
        except Exception:
            # Some responses differ: try dict access
            return resp["choices"][0]["message"]["content"].strip()
    except Exception as modern_exc:
        logger.debug("Modern OpenAI client call failed or not available: %s", modern_exc)

    # Fallback to legacy openai API if available (older openai versions)
    try:
        # prefer ChatCompletion if present
        if hasattr(openai, "ChatCompletion"):
            resp = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        # older versions may use openai.Completion with prompt; we don't support that here
    except Exception as legacy_exc:
        logger.debug("Legacy openai.ChatCompletion call failed: %s", legacy_exc)

    # If both attempts failed, raise
    raise RuntimeError("No compatible OpenAI client available or API call failed. See logs for details.")

def summarize_contract(text: str, style: str = "medium", model: str = "gpt-3.5-turbo"):
    """
    Summarize a contract into plain English.
    style: "short", "medium", "detailed"  (controls length)
    model: model name to use (default gpt-3.5-turbo for test phase)
    """
    style = (style or "medium").lower()
    if style not in ("short", "medium", "detailed"):
        style = "medium"

    # Length-specific instruction (short/medium/detailed)
    if style == "short":
        length_instruction = "Please produce a very concise summary (about 1–2 short paragraphs)."
    elif style == "detailed":
        length_instruction = "Please produce a comprehensive detailed summary covering parties, obligations, deadlines, penalties, payment terms, and any notable risks or unusual clauses."
    else:  # medium
        length_instruction = "Please produce a balanced summary (concise paragraphs highlighting key clauses, obligations and important risks)."

    # Compose messages: system role + user role that includes length instruction and full text
    system_msg = {
        "role": "system",
        "content": "You are a helpful legal assistant that summarizes contracts into plain English."
    }
    user_msg = {
        "role": "user",
        "content": f"{length_instruction}\n\nContract text:\n{text}"
    }

    messages = [system_msg, user_msg]

    max_tokens = LENGTH_TO_MAX_TOKENS.get(style, 800)

    try:
        result_text = _call_openai_chat(messages, model=model, max_tokens=max_tokens, temperature=0.3)
        return result_text
    except Exception as e:
        logger.exception("summarize_contract: OpenAI call failed: %s", e)
        # Raise so app.py's try/except can surface a user-friendly message
        raise RuntimeError(f"AI summarization error: {e}")
