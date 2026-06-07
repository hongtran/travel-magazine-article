import uuid
from datetime import datetime
from pydantic import BaseModel

class BodySection(BaseModel):
    heading: str
    content: str
    source_quote: str

class KeyFact(BaseModel):
    label: str
    value: str
    source_quote: str

class ListItem(BaseModel):
    value: str
    source_quote: str

class ArticleStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    error_message: str | None

class ArticleListItem(BaseModel):
    id: uuid.UUID
    status: str
    original_filename: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

class ArticleResponse(BaseModel):
    id: uuid.UUID
    status: str
    original_filename: str
    original_text: str
    title: str | None
    intro_hook: str | None
    intro_hook_source_quote: str | None
    body_sections: list[BodySection] | None
    best_for: list[ListItem] | None
    not_for: list[ListItem] | None
    ethics_safety_notes: str | None
    ethics_safety_notes_source_quote: str | None
    key_facts: list[KeyFact] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ArticleUpdate(BaseModel):
    title: str | None = None
    intro_hook: str | None = None
    intro_hook_source_quote: str | None = None
    body_sections: list[BodySection] | None = None
    best_for: list[ListItem] | None = None
    not_for: list[ListItem] | None = None
    ethics_safety_notes: str | None = None
    ethics_safety_notes_source_quote: str | None = None
    key_facts: list[KeyFact] | None = None
