# utils/parser.py
# Text extraction + OCR helpers
import io
import pdfplumber
from docx import Document
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image


def _read_bytes(file):
    """
    Accepts either a file path (str) or a file-like object (Streamlit upload).
    Returns bytes.
    """
    if isinstance(file, str):
        with open(file, "rb") as f:
            return f.read()
    else:
        # Streamlit's uploaded file supports .read()
        file_bytes = file.read()
        # If the caller wants to reuse the file later, they may need to reset the pointer.
        try:
            file.seek(0)
        except Exception:
            pass
        return file_bytes


def extract_text_from_pdf(file):
    """
    Extract text from a PDF (if text is selectable).
    `file` can be a path (str) or a file-like object (streamlit upload).
    """
    b = _read_bytes(file)
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        # Reraise so caller can decide whether to fallback to OCR
        raise e
    return text


def extract_text_from_docx(file):
    """
    Extract text from a DOCX file. file can be path or file-like object.
    """
    b = _read_bytes(file)
    doc = Document(io.BytesIO(b))
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paragraphs)


def extract_text_from_scanned_pdf(file):
    """
    OCR the pages of a scanned PDF (or image-only PDF).
    Returns the concatenated text.
    """
    b = _read_bytes(file)
    images = convert_from_bytes(b)  # returns list of PIL.Image
    full_text = ""
    for img in images:
        txt = pytesseract.image_to_string(img)
        full_text += txt + "\n"
    return full_text


def extract_text_from_image(file):
    """
    OCR an image (png/jpg/jpeg). file can be path or file-like.
    """
    b = _read_bytes(file)
    img = Image.open(io.BytesIO(b))
    return pytesseract.image_to_string(img)
