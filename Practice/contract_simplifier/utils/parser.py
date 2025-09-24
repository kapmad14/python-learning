import requests
from io import BytesIO
from docx import Document
import pdfplumber
import streamlit as st

# ----------------------
# PDF / DOCX extraction
# ----------------------
def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        pages = [page.extract_text() for page in pdf.pages]
    return "\n".join(filter(None, pages))

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

# ----------------------
# Cloud OCR extraction
# ----------------------
OCR_SPACE_API_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")  # Add your key in Streamlit Secrets

def ocr_space_file(file):
    """Send file to OCR.Space API and return recognized text"""
    if not OCR_SPACE_API_KEY:
        st.error("OCR API key not found in secrets")
        return ""
    url = "https://api.ocr.space/parse/image"
    payload = {"apikey": OCR_SPACE_API_KEY, "language": "eng"}
    files = {"file": file.getvalue()}  # BytesIO object
    response = requests.post(url, files=files, data=payload)
    result = response.json()
    if result["IsErroredOnProcessing"]:
        st.error(result.get("ErrorMessage", "OCR failed"))
        return ""
    parsed_text = ""
    for item in result["ParsedResults"]:
        parsed_text += item["ParsedText"] + "\n"
    return parsed_text

def extract_text_from_image(file):
    """Extract text from image using OCR.Space"""
    return ocr_space_file(file)

def extract_text_from_scanned_pdf(file):
    """Convert PDF pages to images then send to OCR.Space"""
    from pdf2image import convert_from_bytes

    text = ""
    images = convert_from_bytes(file.getvalue())
    for img in images:
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        text += ocr_space_file(buf) + "\n"
    return text
