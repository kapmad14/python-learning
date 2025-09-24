# utils/ai_processor.py
# OpenAI summarization wrapper (uses OpenAI Python >=1.0.0 interface)
import os
import openai

# --- CONFIG ---
# For local testing you can hard-code your key here.
# For production use environment variables or Streamlit secrets.
OPENAI_API_KEY_HARDCODE = "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"
# Example: OPENAI_API_KEY_HARDCODE = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Prefer environment variable, fallback to hard-coded (if provided)
openai.api_key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY_HARDCODE


def summarize_contract(text, model="gpt-3.5-turbo", max_tokens=1000):
    """
    Summarize contract text into plain English with focus on obligations, deadlines, penalties, termination, renewal.
    Returns a string summary.
    """
    if not openai.api_key:
        raise RuntimeError("OpenAI API key not set. Set OPENAI_API_KEY env var or hard-code for testing.")

    prompt = f"""
You are a helpful legal assistant. Read the contract below and produce a plain-English summary.
Keep it concise but cover: parties, obligations, deadlines, payment terms, penalties/liabilities, termination/renewal, and any critical risk.
Also return a short "Key Clauses" list with clause name and short one-line extraction.

Contract:
{text}
"""

    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=max_tokens
    )

    # the response shape: resp.choices[0].message.content
    return resp.choices[0].message.content
