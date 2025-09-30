# utils/ai_processor.py
import openai
import streamlit as st
import os

# Load API key
if "OPENAI_API_KEY" in st.secrets:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
else:
    openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_contract(text, style="medium"):
    """
    Summarize a contract into plain English.
    style: "short", "medium", "detailed"
    """

    # Adjust style-specific instructions
    if style == "short":
        style_prefix = (
            "Provide a very brief summary (1–2 paragraphs) highlighting the core purpose, "
            "parties involved, and key obligations."
        )
    elif style == "detailed":
        style_prefix = (
            "Provide a comprehensive plain-English summary. Cover parties, obligations, "
            "deadlines, penalties, payment terms, and any risks or unusual clauses."
        )
    else:  # default medium
        style_prefix = (
            "Provide a balanced plain-English summary highlighting key clauses, obligations, "
            "and important risks in a concise manner."
        )

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",   # Using cheaper model for testing
            messages=[
                {"role": "system", "content": "You are a legal assistant specializing in contract simplification."},
                {"role": "user", "content": f"{style_prefix}\n\nContract text:\n{text}"}
            ],
            max_tokens=800,
            temperature=0.5,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"AI summarization failed: {str(e)}"
