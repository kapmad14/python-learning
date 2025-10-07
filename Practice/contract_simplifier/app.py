# app.py
import streamlit as st
import sys
import os
import io
import hashlib
import logging

# ensure utils folder is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "utils")))

from parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_scanned_pdf,
    extract_text_from_image,
)
from ai_processor import summarize_contract
from auth import register_user, validate_user, get_user_plan, ensure_default_user, increment_usage, get_usage

# Setup logging (Streamlit captures stdout/stderr)
logger = logging.getLogger("contract_simplifier")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Ensure default test user exists
ensure_default_user()

st.set_page_config(page_title="Contract Simplifier", layout="wide")

# -----------------------
# Helpers
# -----------------------
def compute_bytes_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

@st.cache_data(show_spinner=False)
def cached_summarize(file_hash: str, format_style: str, length: str, prompt_text: str):
    """
    Cache wrapper around the summarizer. Keyed by file_hash + format_style + length.
    Returns summary string.
    """
    # We pass the full prompt_text (which includes the format-style prefix and the contract text)
    # to summarize_contract, and let the summarizer also receive the length instruction via the
    # 'length' parameter (ai_processor.summarize_contract handles the length parameter).
    return summarize_contract(prompt_text, style=length)

def make_pdf_bytes(text: str, title: str = "Summary") -> bytes:
    """
    Try to create a PDF from text using fpdf. If fpdf not installed, raise ImportError.
    Returns bytes of the PDF.
    """
    try:
        from fpdf import FPDF
    except ImportError as ie:
        raise ie

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, title, ln=1)
    pdf.multi_cell(0, 8, text)
    return pdf.output(dest='S').encode('latin-1')  # return bytes

# -----------------------
# Configuration: limits (change as needed)
# -----------------------
MAX_FREE_BYTES = 4 * 1024 * 1024  # 4 MB free upload limit (adjustable)

# -----------------------
# Session state initialization
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# page state controls which pane is shown; default to Upload
if "page" not in st.session_state:
    st.session_state.page = "Upload"

# Shared state for extracted text & summary
if "last_file_hash" not in st.session_state:
    st.session_state.last_file_hash = None
if "last_text" not in st.session_state:
    st.session_state.last_text = ""
if "last_summary" not in st.session_state:
    st.session_state.last_summary = ""
if "last_style" not in st.session_state:
    st.session_state.last_style = None
# summary length stored in session (short/medium/detailed)
if "last_length" not in st.session_state:
    st.session_state.last_length = "medium"

if "orig_word_count" not in st.session_state:
    st.session_state.orig_word_count = 0
if "summary_word_count" not in st.session_state:
    st.session_state.summary_word_count = 0

# -----------------------
# Authentication flow (login + register)
# -----------------------
if not st.session_state.logged_in:
    st.header("🔐 Login or Register (test stage)")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted_login = st.form_submit_button("Login")
    if submitted_login:
        if validate_user(username, password):
            st.session_state.logged_in = True
            st.session_state.user = username
            # silent reload into main app view
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.write("---")

    st.subheader("🆕 Register a new test user")
    with st.form("reg_form"):
        r_user = st.text_input("Choose username", key="ruser")
        r_pass = st.text_input("Choose password", type="password", key="rpass")
        r_plan = st.selectbox("Plan (for testing)", ["free", "paid"])
        submitted_reg = st.form_submit_button("Register")
    if submitted_reg:
        try:
            register_user(r_user, r_pass, plan=r_plan)
            st.success("User created. Please login from the Login form.")
            # keep previous behavior: do not auto-login after register
        except ValueError as e:
            st.error(str(e))

    st.stop()  # don't render the app below when not logged in

# -----------------------
# Main App (after login)
# -----------------------
# Sidebar: user info, plan, logout
st.sidebar.write(f"Signed in as: **{st.session_state.user}**")
user_plan = get_user_plan(st.session_state.user) or "free"
st.sidebar.write(f"Plan: **{user_plan}**")

# show usage (in-memory)
try:
    usage = get_usage(st.session_state.user)
    st.sidebar.write(f"Uploads: **{usage.get('uploads', 0)}**, Summaries: **{usage.get('summaries', 0)}**")
except Exception:
    logger.exception("get_usage failed")
    st.sidebar.write("Uploads: **0**, Summaries: **0**")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.page = "Upload"
    st.rerun()

# Header
st.title("📄 Contract Simplifier")
st.caption("Upload a contract (PDF/DOCX/Image) and get a clear, structured plain-English summary.")

# Page selector (radio) — keeps programmatic switching capability
page = st.radio("", ["Upload", "Summary", "Analysis"], index=["Upload","Summary","Analysis"].index(st.session_state.page))
if page != st.session_state.page:
    st.session_state.page = page

# -----------------------
# UPLOAD PAGE
# -----------------------
if st.session_state.page == "Upload":
    st.header("1) Upload document / image 📤")
    st.write("Supported: PDF (text or scanned), DOCX, JPG, PNG. Scanned PDFs/images use cloud OCR (OCR.Space).")

    uploaded_file = st.file_uploader(
        "Choose file", type=["pdf", "docx", "png", "jpg", "jpeg"], accept_multiple_files=False
    )

    # Format style selector changed to radio buttons (user requested)
    style_options = ["Detailed Summary", "Bullet Points", "Executive Overview"]
    try:
        default_index = style_options.index(st.session_state.last_style) if st.session_state.last_style in style_options else 0
    except Exception:
        default_index = 0
    format_style = st.radio(
        "Summarization style",
        style_options,
        index=default_index,
        help="Choose how the summary should be written."
    )

    # Summary length selector (short / medium / detailed)
    length = st.selectbox(
        "Summary length",
        ("short", "medium", "detailed"),
        index=("short", "medium", "detailed").index(st.session_state.last_length),
        help="Choose summary length: short / medium / detailed."
    )
    st.write("")  # spacing

    if not uploaded_file:
        st.info("Please upload a PDF, DOCX, or image file to proceed.")
    else:
        # Read bytes once
        try:
            file_bytes = uploaded_file.getvalue()
        except Exception as e:
            st.error("Could not read uploaded file. Please try again.")
            logger.exception("Failed to read uploaded_file: %s", e)
            file_bytes = None

        if file_bytes:
            file_size = len(file_bytes)
            if user_plan == "free" and file_size > MAX_FREE_BYTES:
                st.error(
                    f"Free plan allows files up to {MAX_FREE_BYTES // 1024 // 1024} MB. "
                    f"Your file is {file_size // 1024 // 1024} MB. Please upgrade or upload a smaller file."
                )
                st.stop()

            file_hash = compute_bytes_hash(file_bytes)
            st.session_state.last_file_hash = file_hash
            bio = io.BytesIO(file_bytes)
            bio.name = uploaded_file.name  # help parser/or OCR know file extension

            # Extract text using your parser (which now tries pdfplumber then OCR.Space)
            text = ""
            file_ext = uploaded_file.name.split(".")[-1].lower()
            try:
                with st.spinner("Extracting text from the document (this may take a moment)..."):
                    if file_ext == "docx":
                        text = extract_text_from_docx(bio)
                    elif file_ext == "pdf":
                        # extract_text_from_pdf in your parser does both text-extract and OCR fallback
                        text = extract_text_from_pdf(bio)
                    elif file_ext in ("png", "jpg", "jpeg"):
                        text = extract_text_from_image(bio)
                    else:
                        st.error("Unsupported file type")
                        text = ""
            except Exception as e:
                st.error("Couldn’t extract text from this file. Please upload a clearer copy or a different format.")
                st.exception(e)
                text = ""

            if not text or not text.strip():
                st.error("No readable text found in the uploaded file.")
                st.session_state.last_text = ""
                st.session_state.last_summary = ""
                st.session_state.orig_word_count = 0
                st.session_state.summary_word_count = 0
            else:
                st.session_state.last_text = text
                st.session_state.last_style = format_style
                st.session_state.last_length = length
                orig_words = len(text.split())
                st.session_state.orig_word_count = orig_words
                st.success(f"Text extracted successfully — approx. {orig_words:,} words.")

                # increment upload usage in-memory
                try:
                    increment_usage(st.session_state.user, uploads=1)
                except Exception:
                    logger.exception("increment_usage failed for upload")

                with st.expander("View extracted text (click to expand)"):
                    st.text_area("Contract Text (extracted)", value=text, height=300)

                # Download extracted text as PDF
                # Download extracted text as PDF
                try:
                    extracted_pdf_bytes = make_pdf_bytes(st.session_state.last_text, title="Extracted Contract Text")
                    st.download_button("⬇️ Download extracted text (pdf)", extracted_pdf_bytes, file_name="extracted_text.pdf", mime="application/pdf")
                except ImportError:
                    st.info("PDF export requires 'fpdf'. Install (`pip install fpdf`) to enable extracted-text PDF download.")
                except Exception as e:
                    # Show a brief user-visible error so it's clear why the button isn't displayed
                    logger.exception("Could not create extracted-text PDF: %s", e)
                    st.error("Could not create extracted-text PDF (encoding or PDF generation error). You can still download the extracted text as TXT below.")
                    # offer TXT download as fallback
                    st.download_button("⬇️ Download extracted text (txt)", st.session_state.last_text or "", file_name="extracted_text.txt", mime="text/plain")


                # Summarize now -> generate summary and show it immediately (no page switch)
                if st.button("Summarize now"):
                    # Build format-style prefix safely (use multi-line strings)
                    if format_style == "Detailed Summary":
                        style_prefix = (
                            "Please produce a detailed plain-English summary covering parties, "
                            "obligations, deadlines, penalties, termination and renewal clauses."
                        )
                    elif format_style == "Bullet Points":
                        style_prefix = (
                            "Please summarize the contract into concise bullet points focusing on "
                            "key obligations, deadlines, penalties, termination and renewal."
                        )
                    else:  # Executive Overview
                        style_prefix = (
                            "Please provide a short executive overview highlighting the most "
                            "critical terms, risks, and actions needed."
                        )

                    # Build prompt_text (format prefix + contract)
                    prompt_text = style_prefix + "\n\nContract:\n" + st.session_state.last_text

                    try:
                        with st.spinner("Generating summary with AI..."):
                            # Use cache keyed by file_hash + format_style + length
                            summary = cached_summarize(st.session_state.last_file_hash, format_style, length, prompt_text)
                        st.session_state.last_summary = summary
                        st.session_state.summary_word_count = len(summary.split())

                        # increment summary usage in-memory
                        try:
                            increment_usage(st.session_state.user, summaries=1)
                        except Exception:
                            logger.exception("increment_usage failed for summary")

                        st.success("Summary generated successfully!")

                        # Immediately show the generated summary on the Upload page
                        st.subheader("AI Summary")
                        st.text_area("Summary (generated)", value=st.session_state.last_summary, height=350)

                        # TXT download
                        st.download_button("⬇️ Download summary (txt)", st.session_state.last_summary, file_name="summary.txt", mime="text/plain")

                        # PDF download (optional, requires fpdf)
                        try:
                            pdf_bytes = make_pdf_bytes(st.session_state.last_summary, title="Contract Summary")
                            st.download_button("⬇️ Download summary (pdf)", pdf_bytes, file_name="summary.pdf", mime="application/pdf")
                        except ImportError:
                            st.info("PDF export requires the 'fpdf' package. Install it (`pip install fpdf`) to enable PDF downloads.")
                        except Exception as e:
                            st.error("Could not generate PDF. You can still download the TXT summary.")
                            st.exception(e)

                    except Exception as e:
                        st.error("AI summarization failed. Please try again or check your API key/limits.")
                        st.exception(e)

# -----------------------
# SUMMARY PAGE
# -----------------------
elif st.session_state.page == "Summary":
    st.header("2) Summary ✍️")
    if not st.session_state.last_text:
        st.info("No document processed yet — upload and extract text in the Upload page first.")
    else:
        st.subheader("Document statistics")
        st.write(f"- Original word count: **{st.session_state.orig_word_count:,}**")

        # character counts and estimated reading time
        orig_chars = len(st.session_state.last_text or "")
        est_orig_minutes = max(1, round(st.session_state.orig_word_count / 200)) if st.session_state.orig_word_count else 0
        st.write(f"- Original characters: **{orig_chars:,}** — estimated read time: **{est_orig_minutes} min**")

        if st.session_state.last_summary:
            st.write(f"- Summary word count: **{st.session_state.summary_word_count:,}**")
            summary_chars = len(st.session_state.last_summary)
            est_summary_minutes = max(1, round(st.session_state.summary_word_count / 200)) if st.session_state.summary_word_count else 0
            st.write(f"- Summary characters: **{summary_chars:,}** — estimated read time: **{est_summary_minutes} min**")
            if st.session_state.orig_word_count > 0:
                pct = 100 * st.session_state.summary_word_count / st.session_state.orig_word_count
                st.write(f"- Compression: **{pct:.1f}%** of original")
        else:
            st.write("- No summary generated yet.")

        st.write("---")
        cur_style = st.session_state.last_style or "Detailed Summary"
        cur_length = st.session_state.last_length or "medium"
        st.write(f"**Selected style:** {cur_style} • **Length:** {cur_length}")

        # If no summary yet, allow generation here (also auto-switches after generation)
        if not st.session_state.last_summary:
            if st.button("Generate summary"):
                if cur_style == "Detailed Summary":
                    style_prefix = (
                        "Please produce a detailed plain-English summary covering parties, "
                        "obligations, deadlines, penalties, termination and renewal clauses."
                    )
                elif cur_style == "Bullet Points":
                    style_prefix = (
                        "Please summarize the contract into concise bullet points focusing on "
                        "key obligations, deadlines, penalties, termination and renewal."
                    )
                else:
                    style_prefix = (
                        "Please provide a short executive overview highlighting the most "
                        "critical terms, risks, and actions needed."
                    )

                prompt_text = style_prefix + "\n\nContract:\n" + st.session_state.last_text
                try:
                    with st.spinner("Generating summary with AI..."):
                        summary = cached_summarize(st.session_state.last_file_hash, cur_style, cur_length, prompt_text)
                    st.session_state.last_summary = summary
                    st.session_state.summary_word_count = len(summary.split())

                    # increment summary usage in-memory
                    try:
                        increment_usage(st.session_state.user, summaries=1)
                    except Exception:
                        logger.exception("increment_usage failed for summary (generate)")

                    st.success("Summary generated successfully!")
                    # remain on Summary page and rerun
                    st.session_state.page = "Summary"
                    st.rerun()
                except Exception as e:
                    st.error("AI summarization failed. Please try again later.")
                    st.exception(e)

        # Display summary if available
        if st.session_state.last_summary:
            st.subheader("Plain-English Summary")
            st.text_area("Summary", value=st.session_state.last_summary, height=350)

            # TXT download
            st.download_button("⬇️ Download summary (txt)", st.session_state.last_summary, file_name="summary.txt", mime="text/plain")

            # PDF download (optional, requires fpdf)
            try:
                pdf_bytes = make_pdf_bytes(st.session_state.last_summary, title="Contract Summary")
                st.download_button("⬇️ Download summary (pdf)", pdf_bytes, file_name="summary.pdf", mime="application/pdf")
            except ImportError:
                st.info("PDF export requires the 'fpdf' package. Install it (`pip install fpdf`) to enable PDF downloads.")
            except Exception as e:
                st.error("Could not generate PDF. You can still download the TXT summary.")
                st.exception(e)

# -----------------------
# ANALYSIS PAGE
# -----------------------
else:  # Analysis
    st.header("3) Analysis 🔍")
    st.write("This page will show structured insights (clause extraction, risk scoring) in future versions.")
    if st.session_state.last_summary:
        st.write("Quick highlights (auto-generated):")
        try:
            lines = st.session_state.last_summary.strip().splitlines()
            highlights = lines[:3] if lines else []
            for i, hl in enumerate(highlights, start=1):
                st.markdown(f"**{i}.** {hl}")
        except Exception:
            st.info("No highlights available.")
    else:
        st.info("Generate a summary first to see analysis highlights.")
