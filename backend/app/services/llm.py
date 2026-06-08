import json
import openai
from openai import OpenAI


class LLMError(Exception):
    pass


class LLMTransientError(LLMError):
    """Temporary failure that may resolve on retry (rate limit, network, server error)."""
    pass


class LLMPermanentError(LLMError):
    """Permanent failure that will not resolve on retry (auth, content policy, bad request)."""
    pass


_TRANSIENT_EXCEPTIONS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

_PERMANENT_EXCEPTIONS = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.BadRequestError,
    openai.UnprocessableEntityError,
)

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

_VALIDATION_SCHEMA = {
    "name": "travel_validation",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["is_relevant", "reason"],
        "additionalProperties": False,
        "properties": {
            "is_relevant": {"type": "boolean"},
            "reason": {"type": "string"}
        }
    }
}

_VALIDATION_PROMPT = """Determine whether the following document contains genuine notes about a travel experience — visiting a place, doing an activity (tour, hike, dive, cultural experience, accommodation, etc.), or similar content intended for a travel magazine.

Return is_relevant: true only if the document is clearly about a real travel experience.
Return is_relevant: false if it is a corporate report, academic paper, recipe, legal document, CV/resume, piece of fiction, or any other non-travel content.

Provide a brief reason (1–2 sentences)."""


def validate_travel_relevance(text: str, client: OpenAI) -> tuple[bool, str]:
    """Returns (is_relevant, reason). Raises LLMTransientError or LLMPermanentError on failure."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _VALIDATION_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_schema", "json_schema": _VALIDATION_SCHEMA}
        )
        result = json.loads(response.choices[0].message.content)
        return result["is_relevant"], result["reason"]
    except _PERMANENT_EXCEPTIONS as e:
        raise LLMPermanentError(f"API configuration error: {e}") from e
    except Exception as e:
        raise LLMTransientError(f"Validation call failed: {e}") from e


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
        except _PERMANENT_EXCEPTIONS as e:
            raise LLMPermanentError(f"API configuration error: {e}") from e
        except _TRANSIENT_EXCEPTIONS as e:
            last_error = e
        except Exception as e:
            last_error = e
    raise LLMTransientError(f"Failed after 2 attempts: {last_error}")
