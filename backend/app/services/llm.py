import json
from openai import OpenAI

class LLMError(Exception):
    pass

ARTICLE_SCHEMA = {
    "name": "article",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["title", "intro_hook", "body_sections", "best_for", "not_for", "ethics_safety_notes", "key_facts"],
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "intro_hook": {
                "type": "object",
                "required": ["content", "source_quote"],
                "additionalProperties": False,
                "properties": {
                    "content": {"type": "string"},
                    "source_quote": {"type": "string"}
                }
            },
            "body_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["heading", "content", "source_quote"],
                    "additionalProperties": False,
                    "properties": {
                        "heading": {"type": "string"},
                        "content": {"type": "string"},
                        "source_quote": {"type": "string"}
                    }
                }
            },
            "best_for": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["value", "source_quote"],
                    "additionalProperties": False,
                    "properties": {
                        "value": {"type": "string"},
                        "source_quote": {"type": "string"}
                    }
                }
            },
            "not_for": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["value", "source_quote"],
                    "additionalProperties": False,
                    "properties": {
                        "value": {"type": "string"},
                        "source_quote": {"type": "string"}
                    }
                }
            },
            "ethics_safety_notes": {
                "anyOf": [
                    {
                        "type": "object",
                        "required": ["content", "source_quote"],
                        "additionalProperties": False,
                        "properties": {
                            "content": {"type": "string"},
                            "source_quote": {"type": "string"}
                        }
                    },
                    {"type": "null"}
                ]
            },
            "key_facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["label", "value", "source_quote"],
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                        "source_quote": {"type": "string"}
                    }
                }
            }
        }
    }
}

SYSTEM_PROMPT = """You are an editorial assistant for Seek Sophie, a Singapore-based travel marketplace for handpicked experiences across Asia.
Your tone is warm, discerning, and editorial — not generic travel writing.

Given rough notes about a travel experience, extract and structure the content into a magazine article.

Rules:
- Only use information present in the notes. Do not embellish or invent details.
- source_quote must be a verbatim excerpt from the notes that supports the claim. Use an empty string if no specific quote exists.
- ethics_safety_notes must be null unless the notes contain explicit safety or ethical content.
- best_for and not_for must be specific and honest — not marketing copy. 3–5 items each maximum.
- body_sections must be 3–5 sections regardless of how long the notes are. If the notes cover many topics, prioritize the most distinctive and experiential moments. Omit minor logistics and repetitive detail.
- key_facts must be 3–8 items maximum. Pick only the facts most useful to a first-time visitor — skip anything redundant or logistical noise.
- Be selective, not exhaustive. A longer input does not mean a longer article. Edit ruthlessly."""

def generate_article(original_text: str, client: OpenAI) -> dict:
    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Here are the rough notes:\n\n{original_text}"}
                ],
                response_format={"type": "json_schema", "json_schema": ARTICLE_SCHEMA}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            last_error = e
    raise LLMError(f"Failed to generate article: {last_error}")
