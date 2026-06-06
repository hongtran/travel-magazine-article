from docx import Document
from io import BytesIO

class DocumentError(Exception):
    pass

def extract_text(content: bytes) -> str:
    try:
        doc = Document(BytesIO(content))
    except Exception:
        raise DocumentError("Could not read document — is it a valid .docx?")

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise DocumentError("Document appears to be empty")

    return "\n\n".join(paragraphs)
