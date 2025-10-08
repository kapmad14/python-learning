# utils/ai_processor.py
"""
AI summarization helper with robust OpenAI client support and clearer error mapping.
"""

import os
import streamlit as st
import logging

logger = logging.getLogger(__name__)

# Load API key (Streamlit secrets preferred)
OPENAI_KEY = None
if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
    OPENAI_KEY = st.secrets["OPENAI_API_KEY"]
else:
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Lazy import of openai (some environments have multiple versions); we'll handle in _call_openai_chat
try:
    import openai
except Exception:
    openai = None

# Map lengths to token budgets (tune as needed)
LENGTH_TO_MAX_TOKENS = {
    "short": 300,
    "medium": 800,
    "detailed": 1400,
}

def _call_openai_chat(messages, model="gpt-3.5-turbo", max_tokens=800, temperature=0.5):
    """
    Try to call OpenAI chat using modern client or fall back to legacy ChatCompletion.
    Returns assistant text or raises RuntimeError with a friendly message.
    """
    # Try modern client (openai>=1.0)
    try:
        if openai is not None and hasattr(openai, "OpenAI"):
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
                return resp["choices"][0]["message"]["content"].strip()
    except Exception as exc_modern:
        logger.debug("Modern OpenAI client call failed or not available: %s", exc_modern)

    # Fallback to legacy openai.ChatCompletion
    try:
        if openai is not None and hasattr(openai, "ChatCompletion"):
            # set API key if available
            try:
                if OPENAI_KEY:
                    openai.api_key = OPENAI_KEY
            except Exception:
                pass
            resp = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # legacy response
            return resp.choices[0].message.content.strip()
    except Exception as exc_legacy:
        logger.debug("Legacy OpenAI ChatCompletion call failed: %s", exc_legacy)

    # If both fail, raise
    raise RuntimeError("OpenAI client not available or the API call failed. Check logs and your OPENAI_API_KEY.")

def summarize_contract(text: str, style: str = "medium", model: str = "gpt-3.5-turbo"):
    """
    Summarize a contract into plain English.

    style: "short", "medium", "detailed" (controls length/verbosity)
    """
    style = (style or "medium").lower()
    if style not in ("short", "medium", "detailed"):
        style = "medium"

    # Length instruction mapping (keeps format-style prompting done by app)
    if style == "short":
        length_instruction = "Please produce a very concise summary (about 1–2 short paragraphs)."
    elif style == "detailed":
        length_instruction = "Please produce a comprehensive detailed summary covering parties, obligations, deadlines, penalties, payment terms, and any notable risks or unusual clauses."
    else:
        length_instruction = "Please produce a balanced summary highlighting key clauses, obligations, and important risks in a concise manner."

    system_msg = {
        "role": "system",
        "content": "You are a helpful legal assistant that summarizes contracts into plain English."
    }
    user_msg = {
        "role": "user",
        "content": f"{length_instruction}\n\n{text}"
    }
    messages = [system_msg, user_msg]

    max_tokens = LENGTH_TO_MAX_TOKENS.get(style, 800)

    try:
        result_text = _call_openai_chat(messages, model=model, max_tokens=max_tokens, temperature=0.3)
        return result_text
    except Exception as e:
        # Map common messages to user-friendly errors
        msg = str(e)
        if "invalid_api_key" in msg.lower() or "invalid" in msg.lower() and "key" in msg.lower():
            raise RuntimeError("AI authentication failed: invalid OpenAI API key. Please check your key in Streamlit Secrets or environment variables.")
        if "rate limit" in msg.lower() or "rate_limit" in msg.lower():
            raise RuntimeError("AI rate limit reached. Please try again shortly or upgrade your plan.")
        # generic
        logger.exception("summarize_contract error: %s", e)
        raise RuntimeError(f"AI summarization error: {e}")
