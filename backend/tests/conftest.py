import pytest
from docx import Document
from io import BytesIO

def make_docx(text: str) -> bytes:
    doc = Document()
    for paragraph in text.split("\n\n"):
        doc.add_paragraph(paragraph)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

@pytest.fixture
def sample_docx() -> bytes:
    return make_docx("The boat departs Labuan Bajo at 6am.\n\nCosts around 180-220 SGD pp depending on season.\n\nNot great for kids under 10.")
