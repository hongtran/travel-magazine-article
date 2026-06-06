import json
import pytest
from unittest.mock import MagicMock
from app.services.llm import generate_article, LLMError

MOCK_ARTICLE = {
    "title": "The Komodo Crossing",
    "intro_hook": "The boat smells like diesel and possibility.",
    "body_sections": [
        {"heading": "Getting There", "content": "The boat departs Labuan Bajo at 6am.", "source_quote": "departs labuan bajo at 6am"}
    ],
    "best_for": ["Adventure seekers"],
    "not_for": ["Families with young children"],
    "ethics_safety_notes": None,
    "key_facts": [
        {"label": "Price", "value": "SGD 180–220/person", "source_quote": "180-220 SGD pp depending on season"}
    ]
}

def make_mock_client(response_content: str, raises: Exception | None = None):
    mock_client = MagicMock()
    if raises:
        mock_client.chat.completions.create.side_effect = raises
    else:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = response_content
        mock_client.chat.completions.create.return_value = mock_response
    return mock_client

def test_generate_article_returns_parsed_dict():
    client = make_mock_client(json.dumps(MOCK_ARTICLE))
    result = generate_article("rough notes here", client)
    assert result["title"] == "The Komodo Crossing"
    assert len(result["body_sections"]) == 1
    assert result["body_sections"][0]["source_quote"] == "departs labuan bajo at 6am"

def test_generate_article_retries_once_on_failure():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(MOCK_ARTICLE)
    mock_client.chat.completions.create.side_effect = [
        Exception("timeout"),
        mock_response,
    ]
    result = generate_article("rough notes", mock_client)
    assert result["title"] == "The Komodo Crossing"
    assert mock_client.chat.completions.create.call_count == 2

def test_generate_article_raises_llm_error_after_two_failures():
    client = make_mock_client("", raises=Exception("API error"))
    with pytest.raises(LLMError, match="Failed to generate article"):
        generate_article("rough notes", client)
