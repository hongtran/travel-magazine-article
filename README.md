# Travel Magazine Article Generator

Upload rough travel experience notes (`.docx`) and get a fully structured magazine article — title, intro hook, body sections, best-for/not-for lists, ethics notes, and key facts. Fields are editable inline. Articles are saved and can be revisited.

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (local instance, or use Docker: `docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres`)
- OpenAI API key

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set DATABASE_URL and OPENAI_API_KEY

uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Tables are created automatically on first start.

### Frontend

```bash
cd frontend
npm install

# Create .env.local:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
```

Frontend runs at `http://localhost:3000`.

### Running tests

```bash
cd backend
pytest
```

## Architecture Decisions

**Async article generation**
OpenAI calls take 10–30 seconds, which exceeds typical cloud platform timeout limits. The upload endpoint returns immediately with a `202 Accepted` and an article ID. A FastAPI `BackgroundTask` runs the LLM call asynchronously. The frontend polls `/articles/{id}/status` every 2 seconds until status flips to `completed` or `failed`. This avoids gateway timeouts and gives users immediate feedback.

**Controlled input toggle (not contenteditable)**
Inline editing uses a controlled React `<input>`/`<textarea>` that replaces the display element on click. The alternative — `contenteditable` — causes problems with paste-from-Word (injects raw HTML), has cursor instability in React, and makes revert-on-error complex. The toggle approach handles all three cleanly.

**OpenAI structured output with strict JSON schema**
Using `response_format: { type: "json_schema", json_schema: { strict: true, ... } }` guarantees the response matches the expected shape without post-processing or retries for malformed JSON. The schema requires all article fields including `source_quote` on every claim.

**Source attribution as hallucination mitigation**
Every body section and key fact includes a `source_quote` field — the verbatim excerpt from the original notes that supports the claim. This forces the model to ground every statement and makes unsupported claims visible to editors. It's a lightweight mitigation that doesn't require retrieval infrastructure.

## What Was Cut

- **Authentication** — out of scope for a single-user tool
- **Multi-user support** — would require auth and per-user data isolation
- **Image support** — notes are text-only
- **Draft/publish workflow** — editors work directly on the live article
- **Full-text search** — not needed for the article count this tool generates
