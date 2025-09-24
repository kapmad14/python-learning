import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'utils')))

from utils.parser import extract_text_from_pdf, extract_text_from_docx
# from utils.ai_processor import summarize_contract

pdf_text = extract_text_from_pdf("/Users/kapilmadan/Downloads/Test_Contract_Agreement.pdf")
# summary = summarize_contract(text)

print(pdf_text[:250])

doc_text = extract_text_from_docx("/Users/kapilmadan/Downloads/Test_Contract_Agreement.docx")

print(doc_text[:250])