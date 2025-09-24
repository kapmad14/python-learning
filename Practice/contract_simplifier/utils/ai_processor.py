# utils/ai_processor.py
# OpenAI summarization wrapper (uses OpenAI Python >=1.0.0 interface)
import os
import openai
import streamlit as st

# Try Streamlit secrets first, then environment variable for local testing
<<<<<<< Updated upstream
openai.api_key = st.secrets.get("OPENAI_API_KEY")
=======
openai.api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
>>>>>>> Stashed changes

if not openai.api_key:
    st.error("⚠️ OpenAI API key not set. Please set it in Streamlit Secrets or environment variable.")


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
