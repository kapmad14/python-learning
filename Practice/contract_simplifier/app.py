# app.py
import streamlit as st
import sys
import os
import io
import hashlib

# ensure utils folder is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "utils")))

from parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_scanned_pdf,
    extract_text_from_image,
)
from ai_processor import summarize_contract
from auth import register_user, validate_user, get_user_plan, ensure_default_user

# Ensure default test user exists
ensure_default_user()

st.set_page_config(page_title="Contract Simplifier", layout="wide")

# -----------------------
# Helpers
# -----------------------
def compute_bytes_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

@st.cache_data(show_spinner=False)
def cached_summarize(file_hash: str, style: str, text: str):
    """
    Cache wrapper around the summarizer. Keyed by file_hash + style.
    Returns summary string.
    """
    # style is already applied by prefixing instructions into text
    return summarize_contract(text)

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
    # add text in multi_cell
    pdf.multi_cell(0, 8, text)
    return pdf.output(dest='S').encode('latin-1')  # return bytes

# -----------------------
# Session state for login
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# -----------------------
# Authentication flow (login + register)
# -----------------------
if not st.session_state.logged_in:
    st.header("🔐 Login or Register (test stage)")

    # Login form
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

    # Register form
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
            # preserve earlier behaviour: do not auto-login after register
        except ValueError as e:
            st.error(str(e))

# -----------------------
# Main App (after login)
# -----------------------
else:
    # Sidebar user info / logout
    st.sidebar.write(f"Signed in as: **{st.session_state.user}**")
    user_plan = get_user_plan(st.session_state.user) or "free"
    st.sidebar.write(f"Plan: **{user_plan}**")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    # Top header
    st.title("📄 Contract Simplifier")
    st.caption("Upload a contract (PDF/DOCX/Image) and get a clear, structured plain-English summary.")

    # Tabs: Upload | Summary | Analysis
    tab_upload, tab_summary, tab_analysis = st.tabs(["Upload", "Summary", "Analysis"])

    # Shared state for extracted text & summary (kept in session_state)
    if "last_file_hash" not in st.session_state:
        st.session_state.last_file_hash = None
    if "last_text" not in st.session_state:
        st.session_state.last_text = ""
    if "last_summary" not in st.session_state:
        st.session_state.last_summary = ""
    if "last_style" not in st.session_state:
        st.session_state.last_style = None
    if "orig_word_count" not in st.session_state:
        st.session_state.orig_word_count = 0
    if "summary_word_count" not in st.session_state:
        st.session_state.summary_word_count = 0

    # -----------------------
    # UPLOAD TAB
    # -----------------------
    with tab_upload:
        st.header("1) Upload document / image 📤")
        st.write("Supported: PDF (text or scanned), DOCX, JPG, PNG. Scanned PDFs/images use OCR (cloud).")

        uploaded_file = st.file_uploader(
            "Choose file", type=["pdf", "docx", "png", "jpg", "jpeg"], accept_multiple_files=False
        )

        # Summarization style selector
        style = st.selectbox(
            "Summarization style",
            ("Detailed Summary", "Bullet Points", "Executive Overview"),
            help="Choose how the summary should be written."
        )
        st.write("")  # spacing

        if not uploaded_file:
            st.info("Please upload a PDF, DOCX, or image file to proceed.")
        else:
            # Read bytes once and compute hash
            try:
                file_bytes = uploaded_file.getvalue()
            except Exception as e:
                st.error("Could not read uploaded file. Please try again.")
                file_bytes = None

            if file_bytes:
                file_hash = compute_bytes_hash(file_bytes)
                st.session_state.last_file_hash = file_hash
                # Create a BytesIO object to pass to parser functions (they expect file-like)
                bio = io.BytesIO(file_bytes)
                bio.name = uploaded_file.name  # give it a name so OCR code can inspect extension

                # Extract text with spinner and friendly error messages
                text = ""
                file_ext = uploaded_file.name.split(".")[-1].lower()

                try:
                    with st.spinner("Extracting text from the document (this may take a moment)..."):
                        if file_ext == "docx":
                            # docx extraction
                            text = extract_text_from_docx(bio)
                        elif file_ext == "pdf":
                            # try text extraction first (text-based PDFs)
                            text = extract_text_from_pdf(bio)
                            if not text or not text.strip():
                                st.info("No selectable text found in PDF — running OCR (may take longer)...")
                                # pass a fresh BytesIO
                                bio2 = io.BytesIO(file_bytes)
                                bio2.name = uploaded_file.name
                                text = extract_text_from_scanned_pdf(bio2)
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
                    # clear session text
                    st.session_state.last_text = ""
                    st.session_state.last_summary = ""
                    st.session_state.orig_word_count = 0
                    st.session_state.summary_word_count = 0
                else:
                    # Save extracted text into session state for use by other tabs & caching key
                    st.session_state.last_text = text
                    orig_words = len(text.split())
                    st.session_state.orig_word_count = orig_words
                    st.success(f"Text extracted successfully — approx. {orig_words:,} words.")
                    # Keep selected style
                    st.session_state.last_style = style

                    # Show extracted text inside an expander (so page stays clean)
                    with st.expander("View extracted text (click to expand)"):
                        st.text_area("Contract Text (extracted)", value=text, height=300)

                    # If user wants to summarize immediately via Upload tab
                    if st.button("Summarize now"):
                        # Preference: use cache to avoid duplicate OpenAI calls
                        # Build the text with style prefix so existing summarize_contract works unchanged
                        if style == "Detailed Summary":
                            style_prefix = "Please produce a detailed plain-English summary covering parties, obligations, deadlines, penalti_
