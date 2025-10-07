# utils/ai_processor.py
import openai
import streamlit as st
import os

# Load API key: prefer Streamlit secrets, otherwise environment
if "OPENAI_API_KEY" in st.secrets:
    openai.api_key = st.secrets["OPENAI_API_KEY"]
else:
    openai.api_key = os.getenv("OPENAI_API_KEY")

def _build_prompt(contract_text: str, style: str) -> str:
    """
    Build the user prompt based on selected style.
    style: one of "detailed", "bullet", "executive"
    """
    if style == "detailed":
        template = (
            "You are a legal assistant that simplifies contracts into clear, structured plain-English.\n\n"
            "Task:\n"
            "1. Read the CONTRACT below.\n"
            "2. Produce a structured, plain-English summary with the following sections:\n"
            "   - Parties: who the parties are and their roles.\n"
            "   - Term & Effective Date: any effective dates, durations, renewal clauses.\n"
            "   - Key Obligations: for each party, list primary duties and deliverables.\n"
            "   - Payment Terms: amounts, schedules, invoicing, late fees.\n"
            "   - Deadlines & Milestones: explicit dates or timing obligations.\n"
            "   - Termination & Penalties: grounds for termination, notice periods, penalties.\n"
            "   - Risks & Unusual Clauses: highlight anything risky or atypical.\n"
            "   - Actions / Next Steps: 3 practical recommendations the reader should consider.\n"
            "3. Use clear headings, short paragraphs, and numbered lists. Keep legal jargon minimal and explain technical terms in parentheses.\n"
            "4. If a section is not present in the contract, state \"Not found / Not specified\".\n"
            "5. At the end, include a one-line executive summary (1 sentence).\n\n"
            "Contract:\n"
            f"{contract_text}"
        )
    elif style == "bullet":
        template = (
            "You are a legal assistant that summarizes contracts into concise bullet points.\n\n"
            "Task:\n"
            "1. Read the CONTRACT below.\n"
            "2. Produce 10–20 bullet points (each 1–2 lines) that capture:\n"
            "   - Parties and roles (1 bullet),\n"
            "   - 3–6 core obligations (one per bullet),\n"
            "   - Payment terms (1–2 bullets),\n"
            "   - Deadlines/milestones (1–2 bullets),\n"
            "   - Termination/penalties (1–2 bullets),\n"
            "   - Top 3 risks (each a bullet),\n"
            "   - One-line recommended next step.\n"
            "3. Use plain, direct language; avoid long paragraphs. Numbered or dash bullets both OK.\n\n"
            "Contract:\n"
            f"{contract_text}"
        )
    else:  # executive
        template = (
            "You are a legal assistant writing an executive overview of contracts.\n\n"
            "Task:\n"
            "1. Read the CONTRACT below.\n"
            "2. Produce a 3–5 sentence executive summary covering:\n"
            "   - The contract's purpose,\n"
            "   - The parties and the primary obligations,\n            - The top 2 risks/points of attention,\n"
            "   - One recommended action for the executive.\n"
            "3. Keep it non-technical, suitable to paste into an email or README.\n\n"
            "Contract:\n"
            f"{contract_text}"
        )

    return template

def summarize_contract(contract_text: str, style: str = "medium"):
    """
    Summarize a contract into plain English.
    style: "detailed", "bullet", "executive"
    """
    style = (style or "detailed").lower()
    if style not in {"detailed", "bullet", "executive"}:
        style = "detailed"

    prompt = _build_prompt(contract_text, style)

    try:
        # Using older client method that your environment has been using.
        # If you run into API library errors, replace with your environment's required call.
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a legal assistant specializing in contract simplification."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.2,
        )

        # response.choices[0].message.content is typical for chat completion responses
        return response.choices[0].message.content.strip()

    except Exception as e:
        # Keep behavior: return a string indicating failure so UI shows a message
        return f"AI summarization failed: {str(e)}"
