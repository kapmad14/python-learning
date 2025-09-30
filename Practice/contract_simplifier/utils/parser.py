# utils/parser.py
"""
Parser utilities: PDF/DOCX/text extraction and OCR via OCR.Space cloud.
No poppler / pdf2image / tesseract required.

Functions provided:
- extract_text_from_pdf(file)         # accepts file-like (UploadedFile or BytesIO)
- extract_text_from_docx(file)        # accepts file-like
- extract_text_from_image(file)       # accepts file-like (UploadedFile or BytesIO)
- extract_text_from_scanned_pdf(file) # accepts file-like -> uses OCR.Space on PDF bytes
"""

import io
import json
import logging
from typing import Optional

import pdfplumber
import requests
from docx import Document
import streamlit as st

logger = logging.getLogger(__name__)

# Load OCR API key from Streamlit secrets (works locally if you set env or .streamlit/secrets.toml)
OCR_SPACE_API_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")  # keep this empty if you don't want OCR

# ---------- Helper: OCR.Space call (unified for image or PDF) ----------
def ocr_space_request(file_bytes: bytes, filename: str, filetype: Optional[str] = None, language: str = "eng"):
    """
    Send bytes to OCR.Space and return the recognized text (string).
    - file_bytes: raw bytes of the file
    - filename: filename (including extension) to help OCR.Space detect file type
    - filetype: optional explicit file extension (like 'pdf', 'png'); if None, will infer from filename
    """
    if not OCR_SPACE_API_KEY:
        raise RuntimeError("OCR_SPACE_API_KEY not configured in Streamlit secrets.")

    url = "https://api.ocr.space/parse/image"
    payload = {
        "apikey": OCR_SPACE_API_KEY,
        "language": language,
        "isOverlayRequired": False,  # we only need plain text
        # you can add "OCREngine": 2 to use a different engine
    }

    # Provide a file tuple with filename and bytes; let requests set content-type automatically
    files = {
        "file": (filename, file_bytes)
    }

    try:
        resp = requests.post(url, data=payload, files=files, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("OCR.Space request failed: %s", e)
        raise RuntimeError(f"OCR request failed: {e}")

    try:
        result = resp.json()
    except Exception as e:
        logger.exception("OCR.Space did not return JSON: %s", e)
        raise RuntimeError("OCR service returned an unexpected response format.")

    # OCR.Space returns keys: IsErroredOnProcessing, ParsedResults, ErrorMessage
    if result.get("IsErroredOnProcessing", False):
        # Error message may be a list or string
        err = result.get("ErrorMessage")
        if isinstance(err, list):
            err = err[0] if err else "OCR processing error"
        logger.error("OCR.Space returned an error: %s", err)
        raise RuntimeError(f"OCR service error: {err}")

    parsed_text = []
    for pr in result.get("ParsedResults", []):
        parsed_text.append(pr.get("ParsedText", ""))

    return "\n".join(parsed_text).strip()

# ---------- PDF extraction (text-based) ----------
def extract_text_from_pdf(file):
    """
    Try to extract selectable text from a PDF using pdfplumber.
    Accepts: a file-like object (Streamlit uploaded file) or a path-like object.
    Returns empty string on failure / no text.
    """
    try:
        # Ensure we have bytes
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            stream = io.BytesIO(b)
        elif isinstance(file, (bytes, bytearray)):
            stream = io.BytesIO(file)
        else:
            # file path?
            stream = file

        with pdfplumber.open(stream) as pdf:
            pages = []
            for page in pdf.pages:
                try:
                    t = page.extract_text() or ""
                    pages.append(t)
                except Exception as e:
                    logger.exception("pdfplumber page.extract_text failed: %s", e)
                    pages.append("")
        return "\n".join(pages).strip()
    except Exception as e:
        logger.exception("extract_text_from_pdf failed: %s", e)
        return ""

# ---------- DOCX extraction ----------
def extract_text_from_docx(file):
    """
    Extract text from a DOCX file.
    'file' can be a file-like object (UploadedFile) or a path.
    """
    try:
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            stream = io.BytesIO(b)
            doc = Document(stream)
        else:
            doc = Document(file)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs).strip()
    except Exception as e:
        logger.exception("extract_text_from_docx failed: %s", e)
        return ""

# ---------- Image extraction (PNG/JPEG) ----------
def extract_text_from_image(file):
    """
    Send an image (uploaded file or bytes) to OCR.Space and return text.
    """
    try:
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            filename = getattr(file, "name", "image.png")
        elif isinstance(file, (bytes, bytearray)):
            b = file
            filename = "image.png"
        else:
            # not supported type
            raise ValueError("Unsupported image input type for OCR.")

        # Provide the filename (helps OCR.Space detect mime)
        text = ocr_space_request(b, filename)
        return text
    except Exception as e:
        logger.exception("extract_text_from_image failed: %s", e)
        return ""

# ---------- Scanned PDF extraction (use OCR.Space on PDF bytes) ----------
def extract_text_from_scanned_pdf(file):
    """
    Send the PDF bytes directly to OCR.Space (no conversion on host).
    Accepts uploaded file or bytes. Returns extracted text.
    """
    try:
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            filename = getattr(file, "name", "file.pdf")
        elif isinstance(file, (bytes, bytearray)):
            b = file
            filename = "file.pdf"
        else:
            # file path? try reading
            with open(file, "rb") as fh:
                b = fh.read()
            filename = os.path.basename(file)

        # Pass PDF bytes to OCR.Space; ensure filename ends with .pdf
        if not filename.lower().endswith(".pdf"):
            filename = filename + ".pdf"

        text = ocr_space_request(b, filename)
        return text
    except Exception as e:
        logger.exception("extract_text_from_scanned_pdf failed: %s", e)
        return ""

# ---------- Convenience wrapper to automatically handle PDFs (text-first, then OCR) ----------
def extract_text_from_pdf_auto(file):
    """
    Helper that first tries selectable-text extraction, then falls back to OCR on the PDF bytes.
    Keeps same behavior as before but uses cloud OCR instead of local image conversion.
    """
    # Try pdfplumber first
    text = extract_text_from_pdf(file)
    if text and text.strip():
        return text
    # fallback to OCR of PDF bytes
    try:
        return extract_text_from_scanned_pdf(file)
    except Exception as e:
        logger.exception("extract_text_from_pdf_auto fallback OCR failed: %s", e)
        return ""

# Aliases used by app.py (keep function names used earlier)
# If your app calls extract_text_from_pdf(...) directly, keep that name; otherwise update app.py to call extract_text_from_pdf_auto
# I'll keep names consistent: extract_text_from_pdf will try pdfplumber then OCR (auto behavior)
def extract_text_from_pdf(file):
    return extract_text_from_pdf_auto(file)
