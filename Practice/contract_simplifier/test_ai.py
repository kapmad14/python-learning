# app.py
import streamlit as st
import sys
import os
import json


#test
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

# Ensure we have a default user for quick tests
ensure_default_user()

st.set_page_config(page_title="Contract Simplifier", layout="wide")

SESSION_FILE = "session.json"

# -----------------------
# Helpers for persistent session
# -----------------------
def save_session(username):
    with open(SESSION_FILE, "w") as f:
        json.dump({"user": username}, f)

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return data.get("user")
    return None

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# -----------------------
# Session state init
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# Try auto-login if session file exists
if not st.session_state.logged_in:
    remembered_user = load_session()
    if remembered_user:
        st.session_state.logged_in = True
        st.session_state.user = remembered_user

# -----------------------
# Sidebar menu
# -----------------------
menu = st.sidebar.selectbox("Menu", ["Login / Register", "App"])

# -----------------------
# Login & Register page
# -----------------------
if menu == "Login / Register" and not st.session_state.logged_in:
    st.header("Login or Register (test stage)")

    # Login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember = st.checkbox("Remember me")
        submitted_login = st.form_submit_button("Login")

    if submitted_login:
        if validate_user(username, password):
            st.session_state.logged_in = True
            st.session_state.user = username
            if remember:
                save_session(username)
            st.success(f"✅ Logged in as {username}")
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

    st.write("---")

    # Register form
    st.subheader("Register a new test user")
    with st.form("reg_form"):
        r_user = st.text_input("Choose username", key="ruser")
        r_pass = st.text_input("Choose password", type="password", key="rpass")
        r_plan = st.selectbox("Plan (for testing)", ["free", "paid"])
        submitted_reg = st.form_submit_button("Register")

    if submitted_reg:
        try:
            register_user(r_user, r_pass, plan=r_plan)
            st.success("✅ User created. Please login from the Login form.")
        except ValueError as e:
            st.error(str(e))

# -----------------------
# Main App
# -----------------------
elif menu == "App":
    if not st.session_state.logged_in:
        st.warning("⚠️ Please login first from the sidebar (Menu → Login / Register).")
        st.stop()

    st.title("Contract Simplifier MVP")
    st.sidebar.write(f"Signed in as: **{st.session_state.user}**")

    user_plan = get_user_plan(st.session_state.user) or "free"
    st.sidebar.write(f"Plan: **{user_plan}**")

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        clear_session()
        st.rerun()

    st.header("Upload contract (PDF / DOCX / image)")

    uploaded_file = st.file_uploader(
        "Choose file", type=["pdf", "docx", "png", "jpg", "jpeg"], accept_multiple_files=False
    )

    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()
        try:
            # Handle DOCX
            if file_type == "docx":
                text = extract_text_from_docx(uploaded_file)
            elif file_type == "pdf":
                # try text extraction first
                text = extract_text_from_pdf(uploaded_file)
                if not text or not text.strip():
                    # fallback to OCR
                    st.info("No selectable text found in PDF — running OCR (may take longer)...")
                    text = extract_text_from_scanned_pdf(uploaded_file)
            elif file_type in ("png", "jpg", "jpeg"):
                text = extract_text_from_image(uploaded_file)
            else:
                st.error("❌ Unsupported file type")
                text = None

            if not text or not text.strip():
                st.error("❌ No text could be extracted from the file.")
            else:
                st.subheader("Extracted Text")
                st.text_area("Contract Text", value=text, height=250)

                # Optional gating: for free plan, restrict very long contracts
                if user_plan == "free" and len(text) > 50_000:
                    st.warning("⚠️ Free plan limits long contracts. Upgrade to paid for large uploads.")
                else:
                    if st.button("Summarize Contract"):
                        with st.spinner("🤖 Generating summary..."):
                            try:
                                summary = summarize_contract(text)
                            except Exception as e:
                                st.error(f"AI summarization failed: {e}")
                                summary = None

                        if summary:
                            st.subheader("Plain-English Summary")
                            st.text_area("Summary", value=summary, height=250)

                            # Download summary button
                            st.download_button("⬇️ Download summary (txt)", summary, file_name="summary.txt")
        except Exception as e:
            st.error(f"⚠️ Error processing file: {e}")
