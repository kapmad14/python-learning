# app.py
import streamlit as st
import sys
import os

# Add utils folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "utils")))

from parser import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_image,
    extract_text_from_scanned_pdf
)
from ai_processor import summarize_contract
from auth import register_user, validate_user, get_user_plan, ensure_default_user

# Ensure default test user exists
ensure_default_user()

# Streamlit page config
st.set_page_config(page_title="Contract Simplifier", layout="wide")

# -----------------------
# Session state initialization
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# -----------------------
# Sidebar menu
# -----------------------
menu = st.sidebar.selectbox("Menu", ["Login / Register", "App"])

# -----------------------
# Login / Register
# -----------------------
if menu == "Login / Register":
    st.header("Login or Register (test stage)")

    # Login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted_login = st.form_submit_button("Login")
    if submitted_login:
        if validate_user(username, password):
            st.session_state.logged_in = True
            st.session_state.user = username
            st.success(f"Logged in as {username}")
            st.experimental_rerun()  # reload to show main app
        else:
            st.error("Invalid credentials")

    st.write("---")

    # Registration form
    st.subheader("Register a new test user")
    with st.form("reg_form"):
        r_user = st.text_input("Choose username", key="ruser")
        r_pass = st.text_input("Choose password", type="password", key="rpass")
        r_plan = st.selectbox("Plan (for testing)", ["free", "paid"])
        submitted_reg = st.form_submit_button("Register")
    if submitted_reg:
        try:
            register_user(r_user, r_pass, plan=r_plan)
            st.success("User created. Please login from the Login form.")
        except ValueError as e:
            st.error(str(e))

# -----------------------
# Main app functionality
# -----------------------
else:
    if not st.session_state.logged_in:
        st.warning("Please login first from the sidebar (Menu → Login / Register).")
        st.stop()

    st.sidebar.write(f"Signed in as: **{st.session_state.user}**")
    user_plan = get_user_plan(st.session_state.user) or "free"
    st.sidebar.write(f"Plan: **{user_plan}**")

    st.title("Contract Simplifier MVP")
    st.write(f"Welcome, **{st.session_state.user}**!")

    # -----------------------
    # File upload
    # -----------------------
    uploaded_file = st.file_uploader(
        "Upload contract (PDF / DOCX / image)", 
        type=["pdf", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=False
    )

    if not uploaded_file:
        st.warning("Please upload a PDF, DOCX, or image file to proceed.")
        st.stop()

    # -----------------------
    # Determine file type
    # -----------------------
    file_type = uploaded_file.name.split(".")[-1].lower()
    if file_type not in ("pdf", "docx", "png", "jpg", "jpeg"):
        st.error(f"Unsupported file type: {file_type}. Please upload PDF, DOCX, or image.")
        st.stop()

    # -----------------------
    # Extract text
    # -----------------------
    try:
        if file_type == "docx":
            text = extract_text_from_docx(uploaded_file)
        elif file_type == "pdf":
            text = extract_text_from_pdf(uploaded_file)
            if not text.strip():
                st.info("No selectable text found in PDF — running OCR (may take longer)...")
                text = extract_text_from_scanned_pdf(uploaded_file)
        else:  # images
            text = extract_text_from_image(uploaded_file)

        if not text.strip():
            st.error("No text could be extracted from the uploaded file.")
            st.stop()

        st.subheader("Extracted Text")
        st.text_area("Contract Text", value=text, height=250)

    except Exception as e:
        st.error(f"Error processing file: {e}")
        st.stop()

    # -----------------------
    # Summarize
    # -----------------------
    if st.button("Summarize"):
        if not text.strip():
            st.warning("No text available to summarize.")
        else:
            with st.spinner("Generating summary..."):
                try:
                    summary = summarize_contract(text)
                except Exception as e:
                    st.error(f"AI summarization failed: {e}")
                    summary = None

            if summary:
                st.subheader("Plain-English Summary")
                st.text_area("Summary", value=summary, height=250)
                st.download_button("Download summary (txt)", summary, file_name="summary.txt")

    # -----------------------
    # Logout
    # -----------------------
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.experimental_rerun()
