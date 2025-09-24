# utils/parser.py
import pdfplumber
from docx import Document
from io import BytesIO
import requests
import streamlit as st
from pdf2image import convert_from_bytes

# ----------------------
# PDF extraction
# ----------------------
def extract_text_from_pdf(file):
    """Extract text from a regular PDF"""
    try:
        with pdfplumber.open(file) as pdf:
            pages = [page.extract_text() for page in pdf.pages]
        return "\n".join(filter(None, pages))
    except Exception as e:
        st.error(f"PDF extraction failed: {e}")
        return ""

# ----------------------
# DOCX extraction
# ----------------------
def extract_text_from_docx(file):
    """Extract text from a DOCX file"""
    try:
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.error(f"DOCX extraction failed: {e}")
        return ""

# ----------------------
# OCR.Space cloud OCR
# ----------------------
OCR_SPACE_API_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")

def ocr_space_file(file, file_type=None):
    """
    Send file to OCR.Space API and return recognized text
    file: BytesIO object (from st.file_uploader)
    file_type: optional string like 'png', 'jpg', 'pdf'
    """
    if not OCR_SPACE_API_KEY:
        st.error("OCR API key not found in Streamlit Secrets")
        return ""

    if not file_type:
        file_type = "png"  # fallback

    url = "https://api.ocr.space/parse/image"
    payload = {"apikey": OCR_SPACE_API_KEY, "language": "eng"}
    files = {
        "file": (f"file.{file_type}", file.getvalue())
    }

    try:
        response = requests.post(url, files=files, data=payload)
        result = response.json()
    except Exception as e:
        st.error(f"OCR API request failed: {e}")
        return ""

    if result.get("IsErroredOnProcessing", True):
        st.error(result.get("ErrorMessage", ["OCR failed"])[0])
        return ""

    parsed_text = ""
    for item in result.get("ParsedResults", []):
        parsed_text += item.get("ParsedText", "") + "\n"

    return parsed_text

# ----------------------
# Image OCR
# ----------------------
def extract_text_from_image(file):
    """Extract text from image file"""
    file_type = file.name.split(".")[-1].lower()
    return ocr_space_file(file, file_type=file_type)

# ----------------------
# Scanned PDF OCR
# ----------------------
def extract_text_from_scanned_pdf(file):
    """Convert PDF pages to images, then extract text via OCR.Space"""
    try:
        text = ""
        images = convert_from_bytes(file.getvalue())
        for img in images:
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            text += ocr_space_file(buf, file_type="png") + "\n"
        return text
    except Exception as e:
        st.error(f"Scanned PDF OCR failed: {e}")
        return ""
