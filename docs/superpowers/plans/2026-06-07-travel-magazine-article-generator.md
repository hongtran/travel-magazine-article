# Travel Magazine Article Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web tool that converts rough travel experience notes (.docx) into structured magazine articles using OpenAI GPT-4o, with async processing, inline editing, and persistent PostgreSQL storage.

**Architecture:** FastAPI backend handles file upload, docx parsing, OpenAI structured output generation (async via `BackgroundTasks`), and PostgreSQL persistence. Next.js frontend handles upload, processing status via polling, inline editing with controlled input toggles, and article listing.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2 (async + asyncpg), PostgreSQL, OpenAI Python SDK, python-docx, Next.js 14 (App Router), TypeScript, Tailwind CSS

---

## File Structure

```
travel-magazine-article/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app, CORS, lifespan (creates tables on startup)
│   │   ├── config.py          # Pydantic settings (reads .env)
│   │   ├── database.py        # Async engine, session factory, Base
│   │   ├── models.py          # SQLAlchemy Article model
│   │   ├── schemas.py         # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── articles.py    # All 6 endpoints + process_article background task
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── document.py    # docx parsing + validation
│   │       └── llm.py         # OpenAI structured output call + schema
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_document.py
│   │   └── test_llm.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Home: upload dropzone + article list
│   │   └── articles/
│   │       └── [id]/
│   │           └── page.tsx            # Article view + inline edit
│   ├── components/
│   │   ├── UploadDropzone.tsx
│   │   ├── ArticleList.tsx
│   │   ├── ArticleEditor.tsx           # Full editorial layout
│   │   ├── EditableField.tsx           # Controlled input toggle (core reusable)
│   │   └── SourceChip.tsx             # [source] tooltip chip
│   ├── lib/
│   │   └── api.ts                      # Typed fetch wrapper for all FastAPI endpoints
│   ├── next.config.ts
│   ├── package.json
│   └── .env.local.example
└── docs/
    └── superpowers/
        ├── specs/
        └── plans/
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `frontend/` (via create-next-app)
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Create backend directory and requirements**

```bash
mkdir -p backend/app/routers backend/app/services backend/tests
touch backend/app/__init__.py backend/app/routers/__init__.py backend/app/services/__init__.py
```

Create `backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-docx==1.1.2
openai==1.54.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
python-multipart==0.0.12
pydantic-settings==2.6.1
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 2: Create backend .env.example**

Create `backend/.env.example`:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/travel_articles
OPENAI_API_KEY=sk-...
```

- [ ] **Step 3: Install backend dependencies**

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Scaffold Next.js frontend**

```bash
cd .. && npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --no-src-dir \
  --import-alias "@/*"
```

- [ ] **Step 5: Create frontend .env.local.example**

Create `frontend/.env.local.example`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Copy it to the active env file:
```bash
cp frontend/.env.local.example frontend/.env.local
```

- [ ] **Step 6: Commit**

```bash
git add backend/ frontend/ && git commit -m "feat: scaffold backend and frontend"
```

---

### Task 2: Database models and connection

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`

- [ ] **Step 1: Write config.py**

Create `backend/app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    openai_api_key: str

    model_config = {"env_file": ".env"}

settings = Settings()
```

- [ ] **Step 2: Write database.py**

Create `backend/app/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: Write models.py**

Create `backend/app/models.py`:
```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    intro_hook: Mapped[str | None] = mapped_column(Text)
    body_sections: Mapped[list | None] = mapped_column(JSONB)
    best_for: Mapped[list | None] = mapped_column(JSONB)
    not_for: Mapped[list | None] = mapped_column(JSONB)
    ethics_safety_notes: Mapped[str | None] = mapped_column(Text)
    key_facts: Mapped[list | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/database.py backend/app/models.py
git commit -m "feat: add database models and connection"
```

---

### Task 3: Document parsing service

**Files:**
- Create: `backend/app/services/document.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_document.py`

- [ ] **Step 1: Write failing tests for document service**

Create `backend/tests/conftest.py`:
```python
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
```

Create `backend/tests/test_document.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_document.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.document'`

- [ ] **Step 3: Implement document.py**

Create `backend/app/services/document.py`:
```python
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from io import BytesIO

class DocumentError(Exception):
    pass

def extract_text(content: bytes) -> str:
    try:
        doc = Document(BytesIO(content))
    except (PackageNotFoundError, Exception):
        raise DocumentError("Could not read document — is it a valid .docx?")

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise DocumentError("Document appears to be empty")

    return "\n\n".join(paragraphs)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_document.py -v
```

Expected:
```
PASSED tests/test_document.py::test_extract_text_returns_string_from_valid_docx
PASSED tests/test_document.py::test_extract_text_joins_paragraphs_with_newlines
PASSED tests/test_document.py::test_extract_text_raises_on_corrupted_bytes
PASSED tests/test_document.py::test_extract_text_raises_on_empty_docx
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document.py backend/tests/
git commit -m "feat: add document parsing service with tests"
```

---

### Task 4: LLM service

**Files:**
- Create: `backend/app/services/llm.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Write failing tests for LLM service**

Create `backend/tests/test_llm.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_llm.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.llm'`

- [ ] **Step 3: Implement llm.py**

Create `backend/app/services/llm.py`:
```python
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
            "intro_hook": {"type": "string"},
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
            "best_for": {"type": "array", "items": {"type": "string"}},
            "not_for": {"type": "array", "items": {"type": "string"}},
            "ethics_safety_notes": {"anyOf": [{"type": "string"}, {"type": "null"}]},
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
- best_for and not_for must be specific and honest — not marketing copy.
- body_sections should be 3–5 sections covering what the experience is like. Write in warm editorial prose, not bullet points."""

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_llm.py -v
```

Expected:
```
PASSED tests/test_llm.py::test_generate_article_returns_parsed_dict
PASSED tests/test_llm.py::test_generate_article_retries_once_on_failure
PASSED tests/test_llm.py::test_generate_article_raises_llm_error_after_two_failures
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm.py backend/tests/test_llm.py
git commit -m "feat: add LLM service with structured output schema and retry"
```

---

### Task 5: Pydantic schemas

**Files:**
- Create: `backend/app/schemas.py`

- [ ] **Step 1: Write schemas.py**

Create `backend/app/schemas.py`:
```python
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
    body_sections: list[BodySection] | None
    best_for: list[str] | None
    not_for: list[str] | None
    ethics_safety_notes: str | None
    key_facts: list[KeyFact] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ArticleUpdate(BaseModel):
    title: str | None = None
    intro_hook: str | None = None
    body_sections: list[BodySection] | None = None
    best_for: list[str] | None = None
    not_for: list[str] | None = None
    ethics_safety_notes: str | None = None
    key_facts: list[KeyFact] | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat: add Pydantic schemas"
```

---

### Task 6: Articles router

**Files:**
- Create: `backend/app/routers/articles.py`

- [ ] **Step 1: Write the router file**

Create `backend/app/routers/articles.py`:
```python
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI

from ..config import settings
from ..database import AsyncSessionLocal, get_db
from ..models import Article
from ..schemas import ArticleListItem, ArticleResponse, ArticleStatusResponse, ArticleUpdate
from ..services.document import DocumentError, extract_text
from ..services.llm import LLMError, generate_article

router = APIRouter(prefix="/articles", tags=["articles"])

ALLOWED_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


async def process_article(article_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            return
        try:
            client = get_openai_client()
            result = generate_article(article.original_text, client)
            article.title = result["title"]
            article.intro_hook = result["intro_hook"]
            article.body_sections = result["body_sections"]
            article.best_for = result["best_for"]
            article.not_for = result["not_for"]
            article.ethics_safety_notes = result["ethics_safety_notes"]
            article.key_facts = result["key_facts"]
            article.status = "completed"
        except LLMError as e:
            article.status = "failed"
            article.error_message = str(e)
        article.updated_at = datetime.now(timezone.utc)
        await db.commit()


@router.post("", response_model=ArticleStatusResponse, status_code=202)
async def create_article(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(status_code=422, detail="Only .docx files are supported")
    if file.content_type != ALLOWED_MIME:
        raise HTTPException(status_code=422, detail="Only .docx files are supported")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File must be under 10MB")

    try:
        text = extract_text(content)
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    article = Article(original_filename=file.filename, original_text=text)
    db.add(article)
    await db.commit()
    await db.refresh(article)

    background_tasks.add_task(process_article, article.id)
    return ArticleStatusResponse(id=article.id, status=article.status, error_message=None)


@router.get("", response_model=list[ArticleListItem])
async def list_articles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).order_by(Article.created_at.desc()))
    return result.scalars().all()


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/{article_id}/status", response_model=ArticleStatusResponse)
async def get_article_status(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleStatusResponse(id=article.id, status=article.status, error_message=article.error_message)


@router.patch("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: uuid.UUID,
    payload: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None and hasattr(value, "model_dump"):
            setattr(article, field, value.model_dump())
        elif isinstance(value, list):
            setattr(article, field, [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in value
            ])
        else:
            setattr(article, field, value)

    article.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(article)
    return article


@router.post("/{article_id}/retry", response_model=ArticleStatusResponse, status_code=202)
async def retry_article(
    article_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed articles can be retried")

    article.status = "processing"
    article.error_message = None
    article.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(process_article, article.id)
    return ArticleStatusResponse(id=article.id, status="processing", error_message=None)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/articles.py
git commit -m "feat: add articles router with all 6 endpoints and async background processing"
```

---

### Task 7: FastAPI main app

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: Write main.py**

Create `backend/app/main.py`:
```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import articles

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Travel Magazine Article Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Copy .env.example and start the server**

```bash
cd backend && cp .env.example .env
# Edit .env with your actual DATABASE_URL and OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Expected output:
```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 3: Smoke test the API**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

```bash
curl http://localhost:8000/articles
```

Expected: `[]`

- [ ] **Step 4: Run all backend tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add FastAPI main app with CORS and lifespan table creation"
```

---

### Task 8: Frontend API client and types

**Files:**
- Create: `frontend/lib/api.ts`

- [ ] **Step 1: Write api.ts**

Create `frontend/lib/api.ts`:
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type ArticleStatus = "processing" | "completed" | "failed"

export interface BodySection {
  heading: string
  content: string
  source_quote: string
}

export interface KeyFact {
  label: string
  value: string
  source_quote: string
}

export interface Article {
  id: string
  status: ArticleStatus
  original_filename: string
  original_text: string
  title: string | null
  intro_hook: string | null
  body_sections: BodySection[] | null
  best_for: string[] | null
  not_for: string[] | null
  ethics_safety_notes: string | null
  key_facts: KeyFact[] | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ArticleListItem {
  id: string
  status: ArticleStatus
  original_filename: string
  title: string | null
  created_at: string
}

export interface ArticleStatusResponse {
  id: string
  status: ArticleStatus
  error_message: string | null
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  uploadArticle: (file: File): Promise<ArticleStatusResponse> => {
    const form = new FormData()
    form.append("file", file)
    return apiFetch("/articles", { method: "POST", body: form })
  },

  listArticles: (): Promise<ArticleListItem[]> =>
    apiFetch("/articles"),

  getArticle: (id: string): Promise<Article> =>
    apiFetch(`/articles/${id}`),

  getArticleStatus: (id: string): Promise<ArticleStatusResponse> =>
    apiFetch(`/articles/${id}/status`),

  updateArticle: (id: string, data: Partial<Article>): Promise<Article> =>
    apiFetch(`/articles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  retryArticle: (id: string): Promise<ArticleStatusResponse> =>
    apiFetch(`/articles/${id}/retry`, { method: "POST" }),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add typed API client for FastAPI endpoints"
```

---

### Task 9: Home page — upload dropzone and article list

**Files:**
- Create: `frontend/components/UploadDropzone.tsx`
- Create: `frontend/components/ArticleList.tsx`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Write UploadDropzone.tsx**

Create `frontend/components/UploadDropzone.tsx`:
```tsx
"use client"
import { useRef, useState, DragEvent } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function UploadDropzone() {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const handleFile = async (file: File) => {
    setError(null)
    if (!file.name.endsWith(".docx")) {
      setError("Only .docx files are supported")
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10MB")
      return
    }
    setUploading(true)
    try {
      const { id } = await api.uploadArticle(file)
      router.push(`/articles/${id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed")
      setUploading(false)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="w-full">
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
          ${dragging ? "border-amber-500 bg-amber-50" : "border-gray-300 hover:border-amber-400 hover:bg-gray-50"}
          ${uploading ? "opacity-50 pointer-events-none" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        <p className="text-2xl mb-2">📄</p>
        <p className="text-gray-700 font-medium">
          {uploading ? "Uploading…" : "Drop your .docx file here or click to browse"}
        </p>
        <p className="text-sm text-gray-400 mt-1">Max 10MB · .docx only</p>
      </div>
      {error && (
        <p className="mt-3 text-sm text-red-600 text-center">{error}</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Write ArticleList.tsx**

Create `frontend/components/ArticleList.tsx`:
```tsx
"use client"
import Link from "next/link"
import { ArticleListItem } from "@/lib/api"

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  processing: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
}

interface Props {
  articles: ArticleListItem[]
}

export function ArticleList({ articles }: Props) {
  if (articles.length === 0) {
    return <p className="text-gray-400 text-center py-8">No articles yet. Upload your first document above.</p>
  }

  return (
    <div className="divide-y divide-gray-100">
      {articles.map((article) => (
        <Link
          key={article.id}
          href={`/articles/${article.id}`}
          className="flex items-center justify-between py-4 px-2 hover:bg-gray-50 rounded-lg transition-colors group"
        >
          <div>
            <p className="font-medium text-gray-900 group-hover:text-amber-700 transition-colors">
              {article.title ?? article.original_filename}
            </p>
            <p className="text-sm text-gray-400">{article.original_filename}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLES[article.status]}`}>
              {article.status}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(article.created_at).toLocaleDateString()}
            </span>
          </div>
        </Link>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Write app/page.tsx**

Replace `frontend/app/page.tsx`:
```tsx
import { api } from "@/lib/api"
import { UploadDropzone } from "@/components/UploadDropzone"
import { ArticleList } from "@/components/ArticleList"

export default async function HomePage() {
  const articles = await api.listArticles().catch(() => [])

  return (
    <main className="max-w-3xl mx-auto px-4 py-16">
      <div className="mb-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Article Generator</h1>
        <p className="text-gray-500">Upload rough travel notes and get a structured magazine article.</p>
      </div>

      <UploadDropzone />

      <div className="mt-16">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Saved articles</h2>
        <ArticleList articles={articles} />
      </div>
    </main>
  )
}
```

- [ ] **Step 4: Update layout.tsx**

Replace `frontend/app/layout.tsx`:
```tsx
import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"

const geist = Geist({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Seek Sophie · Article Generator",
  description: "Convert rough travel notes into structured magazine articles",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geist.className} bg-white text-gray-900 antialiased`}>
        {children}
      </body>
    </html>
  )
}
```

- [ ] **Step 5: Start frontend and verify home page loads**

```bash
cd frontend && npm run dev
```

Open http://localhost:3000. Expected: upload dropzone renders, article list shows "No articles yet."

- [ ] **Step 6: Commit**

```bash
git add frontend/components/UploadDropzone.tsx frontend/components/ArticleList.tsx frontend/app/page.tsx frontend/app/layout.tsx
git commit -m "feat: add home page with upload dropzone and article list"
```

---

### Task 10: EditableField and SourceChip components

**Files:**
- Create: `frontend/components/EditableField.tsx`
- Create: `frontend/components/SourceChip.tsx`

- [ ] **Step 1: Write EditableField.tsx**

Create `frontend/components/EditableField.tsx`:
```tsx
"use client"
import { useState, useEffect, useRef } from "react"

interface Props {
  value: string
  onSave: (value: string) => Promise<void>
  multiline?: boolean
  placeholder?: string
  className?: string
  displayClassName?: string
}

export function EditableField({
  value,
  onSave,
  multiline = false,
  placeholder = "Click to edit",
  className = "",
  displayClassName = "",
}: Props) {
  const [editing, setEditing] = useState(false)
  const [localValue, setLocalValue] = useState(value)
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const ref = useRef<HTMLTextAreaElement & HTMLInputElement>(null)

  useEffect(() => {
    setLocalValue(value)
  }, [value])

  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const handleSave = async () => {
    setEditing(false)
    if (localValue === value) return
    setSaveState("saving")
    try {
      await onSave(localValue)
      setSaveState("saved")
      setTimeout(() => setSaveState("idle"), 2000)
    } catch {
      setSaveState("error")
      setLocalValue(value)
      setTimeout(() => setSaveState("idle"), 3000)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") handleSave()
    if (e.key === "Escape") {
      setLocalValue(value)
      setEditing(false)
    }
  }

  const sharedInputClass = `w-full bg-amber-50 border border-amber-300 rounded px-2 py-1
    outline-none focus:ring-2 focus:ring-amber-400 resize-none ${className}`

  if (editing) {
    return multiline ? (
      <textarea
        ref={ref as React.Ref<HTMLTextAreaElement>}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        rows={4}
        className={sharedInputClass}
      />
    ) : (
      <input
        ref={ref as React.Ref<HTMLInputElement>}
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className={sharedInputClass}
      />
    )
  }

  return (
    <span
      onClick={() => setEditing(true)}
      title={saveState === "error" ? "Save failed — click to retry" : "Click to edit"}
      className={`
        cursor-text rounded px-1 -mx-1 transition-colors block
        hover:bg-amber-50 hover:outline hover:outline-1 hover:outline-amber-200
        ${saveState === "error" ? "outline outline-1 outline-red-300 bg-red-50" : ""}
        ${displayClassName}
      `}
    >
      {localValue || <span className="text-gray-300 italic">{placeholder}</span>}
    </span>
  )
}
```

- [ ] **Step 2: Write SourceChip.tsx**

Create `frontend/components/SourceChip.tsx`:
```tsx
"use client"
import { useState } from "react"

interface Props {
  quote: string
}

export function SourceChip({ quote }: Props) {
  const [visible, setVisible] = useState(false)

  if (!quote) return null

  return (
    <span className="relative inline-block ml-2">
      <button
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
        className="text-xs text-amber-600 border border-amber-300 rounded px-1.5 py-0.5 hover:bg-amber-50 transition-colors"
      >
        source
      </button>
      {visible && (
        <span className="absolute z-10 bottom-full left-0 mb-2 w-72 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-xl leading-relaxed">
          <span className="font-semibold text-amber-300 block mb-1">From original notes:</span>
          "{quote}"
          <span className="absolute top-full left-4 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/EditableField.tsx frontend/components/SourceChip.tsx
git commit -m "feat: add EditableField and SourceChip components"
```

---

### Task 11: Article editor component and article page

**Files:**
- Create: `frontend/components/ArticleEditor.tsx`
- Create: `frontend/app/articles/[id]/page.tsx`

- [ ] **Step 1: Write ArticleEditor.tsx**

Create `frontend/components/ArticleEditor.tsx`:
```tsx
"use client"
import { useState } from "react"
import { Article, api } from "@/lib/api"
import { EditableField } from "./EditableField"
import { SourceChip } from "./SourceChip"

interface Props {
  initial: Article
  onSaveState?: (state: "idle" | "saving" | "saved" | "error") => void
}

export function ArticleEditor({ initial, onSaveState }: Props) {
  const [article, setArticle] = useState<Article>(initial)
  const [showOriginal, setShowOriginal] = useState(false)

  const save = async (field: keyof Article, value: unknown) => {
    onSaveState?.("saving")
    try {
      const updated = await api.updateArticle(article.id, { [field]: value })
      setArticle(updated)
      onSaveState?.("saved")
    } catch (e) {
      onSaveState?.("error")
      throw e  // re-throw so EditableField can revert its local value
    }
  }

  return (
    <article className="max-w-2xl mx-auto px-4 py-12">
      {/* Title */}
      <EditableField
        value={article.title ?? ""}
        onSave={(v) => save("title", v)}
        placeholder="Article title"
        displayClassName="text-4xl font-bold text-gray-900 mb-6 leading-tight"
        className="text-4xl font-bold"
      />

      {/* Intro hook */}
      <EditableField
        value={article.intro_hook ?? ""}
        onSave={(v) => save("intro_hook", v)}
        multiline
        placeholder="Write a compelling intro hook…"
        displayClassName="text-xl text-gray-600 leading-relaxed mb-10 border-l-4 border-amber-400 pl-4 italic"
        className="text-xl"
      />

      {/* Body sections */}
      {(article.body_sections ?? []).map((section, i) => (
        <div key={i} className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <EditableField
              value={section.heading}
              onSave={(v) => {
                const sections = [...(article.body_sections ?? [])]
                sections[i] = { ...sections[i], heading: v }
                return save("body_sections", sections)
              }}
              displayClassName="text-xl font-semibold text-gray-800"
              className="text-xl font-semibold"
            />
          </div>
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <EditableField
                value={section.content}
                onSave={(v) => {
                  const sections = [...(article.body_sections ?? [])]
                  sections[i] = { ...sections[i], content: v }
                  return save("body_sections", sections)
                }}
                multiline
                displayClassName="text-gray-700 leading-relaxed"
              />
            </div>
            <SourceChip quote={section.source_quote} />
          </div>
        </div>
      ))}

      {/* Best for / Not for */}
      <div className="grid grid-cols-2 gap-6 my-10 p-6 bg-gray-50 rounded-xl">
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Best for</h3>
          <ul className="space-y-1">
            {(article.best_for ?? []).map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                <span className="text-green-500">✓</span>
                <EditableField
                  value={item}
                  onSave={(v) => {
                    const list = [...(article.best_for ?? [])]
                    list[i] = v
                    return save("best_for", list)
                  }}
                  displayClassName="text-sm text-gray-600"
                />
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Not for</h3>
          <ul className="space-y-1">
            {(article.not_for ?? []).map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                <span className="text-red-400">✗</span>
                <EditableField
                  value={item}
                  onSave={(v) => {
                    const list = [...(article.not_for ?? [])]
                    list[i] = v
                    return save("not_for", list)
                  }}
                  displayClassName="text-sm text-gray-600"
                />
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Ethics & Safety */}
      {article.ethics_safety_notes && (
        <div className="my-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <h3 className="font-semibold text-yellow-800 mb-2">Ethics & Safety</h3>
          <EditableField
            value={article.ethics_safety_notes}
            onSave={(v) => save("ethics_safety_notes", v)}
            multiline
            displayClassName="text-sm text-yellow-700"
          />
        </div>
      )}

      {/* Key facts */}
      <div className="my-10">
        <h3 className="font-semibold text-gray-700 mb-3">Key facts</h3>
        <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
          {(article.key_facts ?? []).map((fact, i) => (
            <div key={i} className="flex items-center px-4 py-3 bg-white">
              <EditableField
                value={fact.label}
                onSave={(v) => {
                  const facts = [...(article.key_facts ?? [])]
                  facts[i] = { ...facts[i], label: v }
                  return save("key_facts", facts)
                }}
                displayClassName="text-sm font-medium text-gray-500 w-28 shrink-0"
                className="text-sm w-28"
              />
              <EditableField
                value={fact.value}
                onSave={(v) => {
                  const facts = [...(article.key_facts ?? [])]
                  facts[i] = { ...facts[i], value: v }
                  return save("key_facts", facts)
                }}
                displayClassName="text-sm text-gray-800 flex-1"
                className="text-sm flex-1"
              />
              <SourceChip quote={fact.source_quote} />
            </div>
          ))}
        </div>
      </div>

      {/* Original notes toggle */}
      <div className="mt-12 border-t border-gray-200 pt-8">
        <button
          onClick={() => setShowOriginal((v) => !v)}
          className="text-sm text-gray-400 hover:text-gray-700 transition-colors"
        >
          {showOriginal ? "▲ Hide original notes" : "▼ View original notes"}
        </button>
        {showOriginal && (
          <pre className="mt-4 text-xs text-gray-500 bg-gray-50 rounded-lg p-4 whitespace-pre-wrap leading-relaxed font-mono">
            {article.original_text}
          </pre>
        )}
      </div>
    </article>
  )
}
```

- [ ] **Step 2: Write app/articles/[id]/page.tsx**

Create `frontend/app/articles/[id]/page.tsx`:
```tsx
"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Article, ArticleStatus, api } from "@/lib/api"
import { ArticleEditor } from "@/components/ArticleEditor"

export default function ArticlePage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [article, setArticle] = useState<Article | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle")

  useEffect(() => {
    let cancelled = false
    let pollInterval: ReturnType<typeof setInterval> | null = null

    const loadArticle = async () => {
      try {
        const data = await api.getArticle(id)
        if (cancelled) return
        setArticle(data)

        if (data.status === "processing") {
          pollInterval = setInterval(async () => {
            try {
              const status = await api.getArticleStatus(id)
              if (cancelled) return
              if (status.status === "completed") {
                clearInterval(pollInterval!)
                const full = await api.getArticle(id)
                if (!cancelled) setArticle(full)
              } else if (status.status === "failed") {
                clearInterval(pollInterval!)
                setArticle((prev) => prev ? { ...prev, status: "failed", error_message: status.error_message } : prev)
              }
            } catch {
              // network blip — keep polling
            }
          }, 2000)
        }
      } catch {
        if (!cancelled) setError("Article not found")
      }
    }

    loadArticle()
    return () => {
      cancelled = true
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [id])

  const handleRetry = async () => {
    setError(null)
    await api.retryArticle(id)
    setArticle((prev) => prev ? { ...prev, status: "processing", error_message: null } : prev)
    router.refresh()
  }

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-16 text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href="/" className="text-amber-600 hover:underline">← Back to home</Link>
      </main>
    )
  }

  if (!article) {
    return <ProcessingView message="Loading…" />
  }

  if (article.status === "processing") {
    return <ProcessingView message="Generating your article…" />
  }

  if (article.status === "failed") {
    return (
      <main className="max-w-2xl mx-auto px-4 py-16 text-center">
        <p className="text-red-600 font-medium mb-2">Generation failed</p>
        <p className="text-gray-500 text-sm mb-6">{article.error_message ?? "An unexpected error occurred."}</p>
        <button
          onClick={handleRetry}
          className="bg-amber-600 text-white px-6 py-2 rounded-lg hover:bg-amber-700 transition-colors mr-4"
        >
          Retry
        </button>
        <Link href="/" className="text-gray-400 hover:text-gray-700">← Back</Link>
      </main>
    )
  }

  return (
    <div>
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <Link href="/" className="text-sm text-gray-400 hover:text-gray-700 transition-colors">← All articles</Link>
        <span className={`text-xs font-medium transition-colors ${
          saveState === "saving" ? "text-amber-500" :
          saveState === "saved" ? "text-green-600" :
          saveState === "error" ? "text-red-500" : "text-transparent"
        }`}>
          {saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : saveState === "error" ? "Save failed" : "·"}
        </span>
      </header>
      <ArticleEditor initial={article} onSaveState={setSaveState} />
    </div>
  )
}

function ProcessingView({ message }: { message: string }) {
  return (
    <main className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded mb-4 w-3/4 mx-auto" />
        <div className="h-4 bg-gray-200 rounded mb-2 w-full" />
        <div className="h-4 bg-gray-200 rounded mb-2 w-5/6 mx-auto" />
        <div className="h-4 bg-gray-200 rounded w-4/5 mx-auto" />
      </div>
      <p className="mt-8 text-sm text-gray-400">{message}</p>
    </main>
  )
}
```

- [ ] **Step 3: End-to-end test**

With both servers running (`uvicorn` on 8000, `npm run dev` on 3000):

1. Open http://localhost:3000
2. Upload a `.docx` file with a few paragraphs of travel notes
3. Confirm redirect to `/articles/{id}` with skeleton loading state
4. Wait for status to flip to `completed` (watch backend logs)
5. Confirm article renders with all fields populated
6. Click a field, edit it, blur — confirm "Saving…" / "Saved" indicator
7. Hover a `[source]` chip — confirm tooltip shows original quote
8. Click "View original notes" — confirm raw text expands

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ArticleEditor.tsx frontend/app/articles/
git commit -m "feat: add article page with inline editing, polling, and source attribution"
```

---

### Task 12: Deployment

**Files:**
- Create: `backend/Procfile`
- Create: `README.md`

- [ ] **Step 1: Create backend Procfile for Railway**

Create `backend/Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Update CORS for production**

In `backend/app/main.py`, replace the `allow_origins` line:
```python
allow_origins=[
    "http://localhost:3000",
    os.environ.get("FRONTEND_URL", ""),
],
```

- [ ] **Step 3: Deploy backend to Railway**

1. Push backend to GitHub (or connect Railway to the repo)
2. On Railway: New Project → Deploy from GitHub → select the repo → set root directory to `backend/`
3. Add a PostgreSQL plugin to the Railway project
4. Set environment variables in Railway:
   - `DATABASE_URL` — Railway provides this automatically from the Postgres plugin (copy the internal URL)
   - `OPENAI_API_KEY` — your key
   - `FRONTEND_URL` — your Vercel URL (add after step 5)
5. Verify deploy: `curl https://your-railway-url.up.railway.app/health`

- [ ] **Step 4: Deploy frontend to Vercel**

1. Push frontend to GitHub
2. On Vercel: Import project → select the repo → set root directory to `frontend/`
3. Set environment variable: `NEXT_PUBLIC_API_URL=https://your-railway-url.up.railway.app`
4. Deploy
5. Go back to Railway and set `FRONTEND_URL` to your Vercel URL, then redeploy backend

- [ ] **Step 5: Write README.md**

Create `README.md` at the repo root. Cover:
- What the tool does (1 paragraph)
- Local setup (backend + frontend steps)
- Live demo link
- Architecture decisions made and why (async, controlled input toggle, structured output schema, source attribution as hallucination mitigation)
- What was cut and why

- [ ] **Step 6: Final commit**

```bash
git add backend/Procfile backend/app/main.py README.md
git commit -m "feat: add deployment config and README"
```
