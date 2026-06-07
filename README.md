# Travel Magazine Article Generator

Upload rough travel experience notes (`.docx`) and get a fully structured magazine article — title, intro hook, body sections, best-for/not-for lists, ethics notes, and key facts. Every extracted field carries a source quote traceable to the original notes. Fields are editable inline. Articles are saved and can be revisited.

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (local or Docker: `docker run --name travel-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=travel_articles -p 5432:5432 -d postgres:16`)
- OpenAI API key

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env with:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/travel_articles
# OPENAI_API_KEY=sk-...

uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Tables are created automatically on first start.

### Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Running tests

```bash
cd backend
pytest
```

---

## What It Does

1. **Upload** a `.docx` file of rough travel notes
2. **LLM generates** a structured article: title, hook, 3–5 body sections, best-for/not-for lists, ethics & safety, key facts
3. **Every field is sourced** — a verbatim quote from the original notes is attached to each claim. Fields without a traceable quote surface an amber "unverified" badge
4. **Review and edit** any field inline before saving
5. **Articles persist** and are viewable again later

---

## Architecture Decisions

**Async article generation**
OpenAI calls take 10–30 seconds, exceeding typical cloud platform timeout limits. The upload endpoint returns immediately with `202 Accepted`. A FastAPI `BackgroundTask` runs the LLM call asynchronously. The frontend polls `/articles/{id}/status` every 2 seconds (capped at 150 polls / 5 minutes) until status flips to `completed` or `failed`.

**Source attribution on every field**
Every structured field — not just body sections — carries a `source_quote`: the verbatim excerpt from the original notes that supports the claim. The UI shows a `[source]` chip (hover for quote) when sourced, and an amber `[unverified]` badge when the LLM couldn't find a supporting passage. This makes hallucinations visible at review time without blocking the editor.

**Controlled input toggle (not contenteditable)**
Inline editing uses a controlled React `<input>`/`<textarea>` that replaces the display element on click. `contenteditable` was rejected: paste from Word injects raw HTML, React has cursor instability on re-render, and revert-on-error is complex.

**OpenAI structured output with strict JSON schema**
`response_format: { type: "json_schema", strict: true }` guarantees the response matches the expected shape. Schema violations are caught at the API layer. All fields including `source_quote` are required by the schema.

**Output length discipline over chunking**
The system prompt explicitly caps output regardless of input length: 3–5 body sections, 3–5 best-for/not-for items, 3–8 key facts. "A longer input does not mean a longer article." Chunking was considered and rejected — the real problem is editorial output length, not token limits.

**Cost guardrails**
Two lightweight checks before any LLM call: documents under 50 words are rejected with a 422 (not worth generating from); a daily cap of 20 generations returns 429 when reached. No auth infrastructure required.

---

## What Was Cut

| Cut | Reason |
|-----|--------|
| Authentication | Single-user internal tool |
| Export to Word / PDF | Nice to have, out of scope |
| Edit history / versioning | `updated_at` tracks last save; full versioning is a product decision |
| Image extraction | Article schema has no image field |
| Streaming LLM output | Complicates structured output enforcement; polling gives adequate UX |
| Celery / Redis | `BackgroundTasks` sufficient for one instance; production path is Celery + Redis |
| Chunking long documents | Solved at the prompt level instead |
| Per-user generation limits | No auth = no user identity; global daily cap is sufficient |
