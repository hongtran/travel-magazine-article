import pytest
from tests.conftest import make_docx
from app.services.document import extract_text, DocumentError

def test_extract_text_returns_string_from_valid_docx(sample_docx):
    text = extract_text(sample_docx)
    assert "Labuan Bajo" in text
    assert "180-220 SGD" in text

def test_extract_text_joins_paragraphs_with_newlines(sample_docx):
    text = extract_text(sample_docx)
    assert "\n" in text

def test_extract_text_raises_on_corrupted_bytes():
    with pytest.raises(DocumentError, match="Could not read document"):
        extract_text(b"not a real docx file")

def test_extract_text_raises_on_empty_docx():
    empty = make_docx("")
    with pytest.raises(DocumentError, match="Document appears to be empty"):
        extract_text(empty)
