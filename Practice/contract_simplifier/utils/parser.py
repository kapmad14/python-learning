# utils/parser.py
"""
Parser utilities: PDF/DOCX/text extraction and OCR via OCR.Space cloud.
Fixed to avoid recursion: extract_text_from_pdf is the public function that
tries selectable-text extraction first, then falls back to OCR on PDF bytes.
"""

import io
import logging
from typing import Optional

import pdfplumber
import requests
from docx import Document
import streamlit as st
import os

logger = logging.getLogger(__name__)

# OCR key from Streamlit secrets
OCR_SPACE_API_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")

# ---------- OCR.Space request helper ----------
def ocr_space_request(file_bytes: bytes, filename: str, language: str = "eng"):
    """
    Send bytes to OCR.Space and return recognized text.
    Raises RuntimeError on failure.
    """
    if not OCR_SPACE_API_KEY:
        raise RuntimeError("OCR_SPACE_API_KEY not configured in Streamlit secrets.")

    url = "https://api.ocr.space/parse/image"
    payload = {
        "apikey": OCR_SPACE_API_KEY,
        "language": language,
        "isOverlayRequired": False,
    }
    files = {"file": (filename, file_bytes)}
    try:
        resp = requests.post(url, data=payload, files=files, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("OCR.Space request failed: %s", e)
        raise RuntimeError(f"OCR request failed: {e}") from e

    try:
        result = resp.json()
    except Exception as e:
        logger.exception("OCR.Space returned non-JSON response: %s", e)
        raise RuntimeError("OCR service returned an unexpected response format.") from e

    if result.get("IsErroredOnProcessing", False):
        err = result.get("ErrorMessage")
        if isinstance(err, list):
            err = err[0] if err else "OCR processing error"
        logger.error("OCR.Space returned an error: %s", err)
        raise RuntimeError(f"OCR service error: {err}")

    parsed_texts = []
    for pr in result.get("ParsedResults", []):
        parsed_texts.append(pr.get("ParsedText", ""))

    return "\n".join(parsed_texts).strip()

# ---------- pdfplumber-only extraction helper (internal) ----------
def _extract_text_from_pdf_plumber(file) -> str:
    """
    Use pdfplumber to extract selectable text.
    Accepts file-like (UploadedFile/BytesIO) or path.
    Returns extracted text or empty string on failure/no text.
    """
    try:
        # Prepare a stream for pdfplumber
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            stream = io.BytesIO(b)
        elif isinstance(file, (bytes, bytearray)):
            stream = io.BytesIO(file)
        else:
            # assume file is a path-like object
            stream = file

        with pdfplumber.open(stream) as pdf:
            pages = []
            for page in pdf.pages:
                try:
                    t = page.extract_text() or ""
                    pages.append(t)
                except Exception as e:
                    logger.exception("pdfplumber page.extract_text failed on a page: %s", e)
                    pages.append("")
        return "\n".join(pages).strip()
    except Exception as e:
        logger.exception("pdfplumber extraction failed: %s", e)
        return ""

# ---------- Public PDF extraction (text-first, then OCR fallback) ----------
def extract_text_from_pdf(file) -> str:
    """
    Public helper used by the app.
    Tries pdfplumber first (fast, no external calls). If that yields no text,
    falls back to sending the PDF bytes to OCR.Space (cloud OCR).
    Returns extracted text (possibly empty string on failure).
    """
    try:
        # Try pdfplumber selectable-text extraction first
        text = _extract_text_from_pdf_plumber(file)
        if text and text.strip():
            return text

        # No selectable text found -> fallback to OCR on PDF bytes
        # Prepare bytes and filename
        if hasattr(file, "getvalue"):
            b = file.getvalue()
            filename = getattr(file, "name", "file.pdf")
        elif isinstance(file, (bytes, bytearray)):
            b = file
            filename = "file.pdf"
        else:
            # file is path-like
            with open(file, "rb") as fh:
                b = fh.read()
            filename = os.path.basename(file)

        if not filename.lower().endswith(".pdf"):
            filename = filename + ".pdf"

        try:
            text = ocr_space_request(b, filename)
            return text
        except Exception as e:
            logger.exception("PDF OCR fallback failed: %s", e)
            return ""
    except Exception as e:
        logger.exception("extract_text_from_pdf encountered an unexpected error: %s", e)
        return ""

# ---------- DOCX extraction ----------
def extract_text_from_docx(file) -> str:
    """
    Extract text from a DOCX file. Accepts file-like or path.
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
def extract_text_from_image(file) -> str:
    """
    Send an image (uploaded file or bytes) to OCR.Space and return text.
    """
    try:
        if hasattr(file, "getvalue"):
