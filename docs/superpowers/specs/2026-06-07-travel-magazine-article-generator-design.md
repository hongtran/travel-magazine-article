# Travel Magazine Article Generator — Design Spec

**Date:** 2026-06-07  
**Stack:** Next.js (App Router) + FastAPI + PostgreSQL  
**LLM:** OpenAI GPT-4o with structured outputs  
**Scope:** Pre-interview task, ~4 hours

---

## 1. Problem

Seek Sophie editorial authors convert rough notes (Google Docs, interview transcripts, Slack threads) into structured magazine articles manually. This is slow. The tool replaces the blank-page step: upload rough notes, get a structured draft, review and edit inline, save.

---

## 2. Architecture

```
Browser → Next.js (App Router, pure frontend)
              ↓ fetch
         FastAPI (primary backend)
           ├── python-docx      (docx parsing)
           ├── OpenAI Python SDK (structured generation)
           └── PostgreSQL        (persistence via SQLAlchemy + asyncpg)
```

Next.js has no API routes — FastAPI owns all server-side logic. Clean boundary: Next.js is the client, FastAPI is the server.

### Processing flow

1. User uploads `.docx` → `POST /articles`
2. FastAPI validates file, extracts text, checks word count and daily limit, creates article record with `status=processing`, fires `BackgroundTask`, returns `{id, status}` immediately
3. Background task: parse → OpenAI call → DB update to `status=completed` or `status=failed`
4. Frontend navigates to `/articles/{id}`, polls `/articles/{id}/status` every 2 seconds, up to 150 polls (5 minutes)
5. On `completed`: fetch full article, render editable layout. On `failed`: show error + retry button. On poll cap reached: show "still processing — check back later"

**Why async over sync:** OpenAI calls take 10–30 seconds. Standard hosting platforms (Railway, Render) have HTTP timeout limits around 30–60 seconds. Sync risks silent timeout failures where the result is lost. Async makes the failure surface explicit and recoverable. Trade-off: requires polling logic (~30 lines of frontend code) and a status field on the article record.

**Scaling note:** FastAPI `BackgroundTasks` runs in-process — adequate for a single instance. Production horizontal scaling would require an external queue (Celery + Redis or similar). Worth flagging in the writeup.

---

## 3. Data Model

One table. Structured fields in JSONB for flexibility without migrations.

```sql
CREATE TABLE articles (
  id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status                          TEXT NOT NULL DEFAULT 'processing',
                                  -- 'processing' | 'completed' | 'failed'
  original_filename               TEXT NOT NULL,
  original_text                   TEXT NOT NULL,
  title                           TEXT,
  intro_hook                      TEXT,
  intro_hook_source_quote         TEXT,
  body_sections                   JSONB,
  best_for                        JSONB,
  not_for                         JSONB,
  ethics_safety_notes             TEXT,
  ethics_safety_notes_source_quote TEXT,
  key_facts                       JSONB,
  error_message                   TEXT,
  created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### JSONB shapes

```json
// body_sections
[
  {
    "heading": "Getting There",
    "content": "The boat departs from Labuan Bajo at 6am...",
    "source_quote": "departs labuan bajo early morning, around 6"
  }
]

// key_facts
[
  {
    "label": "Price",
    "value": "SGD 180–220 per person",
    "source_quote": "costs around 180-220 sgd pp depending on season"
  }
]

// best_for / not_for (changed from list[str] to list[{value, source_quote}])
[
  { "value": "Adventure seekers", "source_quote": "we scrambled up rocks for two hours" },
  { "value": "Solo travellers", "source_quote": "" }
]
```

### Design decisions

- `original_text` is stored permanently. Source quotes are only verifiable against the stored raw text — without it, citations are unverifiable.
- `source_quote` is now required on **every structured field** — body sections, key facts, best_for/not_for items, intro hook, and ethics & safety. Not just a few fields.
- `best_for` and `not_for` changed from `list[str]` to `list[{value, source_quote}]` to support per-item attribution.
- `intro_hook_source_quote` and `ethics_safety_notes_source_quote` are separate Text columns rather than changing those fields to JSONB — simpler, no data migration risk.
- `error_message` makes failed generation a queryable state. Articles don't silently disappear on LLM failure.
- `status` is TEXT not a Postgres ENUM — adding a new status value doesn't require `ALTER TYPE`.

---

## 4. API

All endpoints on FastAPI. CORS configured for Next.js origin.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/articles` | Upload `.docx`, kick off processing |
| `GET` | `/articles` | List all articles |
| `GET` | `/articles/{id}` | Full article detail |
| `GET` | `/articles/{id}/status` | Lightweight poll — status + error only |
| `PATCH` | `/articles/{id}` | Save inline edits (partial update) |
| `POST` | `/articles/{id}/retry` | Re-trigger LLM processing on a failed article |

### POST /articles

Validates before any DB write or LLM call:
- Extension is `.docx`
- MIME type is `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- File size ≤ 10MB
- `python-docx` can open it (catches corrupted files)
- Extracted text is ≥ 50 words (catches blank and trivially short documents)
- Daily generation count < 20 (cost cap — checked via `COUNT(*)` on today's rows)

Returns `{id, status: "processing"}` immediately. Frontend navigates and starts polling.

### GET /articles/{id}/status

Returns only `{id, status, error_message}`. Keeps the polling loop lightweight — not re-fetching full JSONB on every tick. Frontend does one full `GET /articles/{id}` when status reaches `completed`.

### PATCH /articles/{id}

Partial update — only fields included in the request body are updated. Inline editing sends one field at a time. Updates `updated_at`. Returns the updated article.

```json
{ "intro_hook": "The boat smells like diesel and possibility..." }
```

### Error responses

| Scenario | Status | Message |
|----------|--------|---------|
| Non-docx file | 422 | `"Only .docx files are supported"` |
| File too large | 413 | `"File must be under 10MB"` |
| Corrupted docx | 422 | `"Could not read document — is it a valid .docx?"` |
| Document too short | 422 | `"Document is too short (N words). Please provide at least 50 words."` |
| Daily limit reached | 429 | `"Daily generation limit of 20 articles reached. Try again tomorrow."` |
| Article not found | 404 | `"Article not found"` |
| OpenAI timeout / bad JSON | stored as `status=failed` | surfaced via `/status` poll |

OpenAI failures do not return 5xx — the upload succeeded. The failure surfaces through the poll as `status=failed` with `error_message`. The frontend offers a retry button that calls `POST /articles/{id}/retry`, which resets status to `processing` and re-fires the background task using the stored `original_text` — no re-upload needed.

---

## 5. LLM Integration

### Structured output schema

OpenAI call uses `response_format` with a strict JSON schema. This enforces structure at the API level — not prose with a schema sprinkled on top.

All fields now return `source_quote`. `intro_hook` and `ethics_safety_notes` return objects; `best_for`/`not_for` return arrays of objects:

```python
{
  "title": {"type": "string"},
  "intro_hook": {
    "type": "object",
    "required": ["content", "source_quote"],
    "properties": {
      "content": {"type": "string"},
      "source_quote": {"type": "string"}
    }
  },
  "best_for": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["value", "source_quote"],
      "properties": { "value": {"type": "string"}, "source_quote": {"type": "string"} }
    }
  },
  "not_for": { /* same as best_for */ },
  "ethics_safety_notes": {
    "anyOf": [
      {
        "type": "object",
        "required": ["content", "source_quote"],
        "properties": { "content": {"type": "string"}, "source_quote": {"type": "string"} }
      },
      {"type": "null"}
    ]
  },
  "body_sections": { /* heading, content, source_quote per section */ },
  "key_facts":     { /* label, value, source_quote per fact */ }
}
```

### Hallucination mitigation

`source_quote` is required on **every extracted field**. The LLM must cite the verbatim sentence from the original notes that supports each claim. Editors see a `[source]` chip on sourced fields and an amber `[unverified]` badge on fields where no quote was found. This makes unsupported claims visible rather than hiding them in fluent prose.

This is not a guarantee — it is a forcing function that surfaces hallucination risk at review time.

### Output length discipline

The system prompt explicitly caps output size regardless of input length:
- `body_sections`: 3–5 sections. Long notes → prioritise most distinctive moments, omit logistics.
- `best_for` / `not_for`: 3–5 items each.
- `key_facts`: 3–8 items. Prioritise facts useful to a first-time visitor.
- Closing instruction: "A longer input does not mean a longer article. Edit ruthlessly."

This replaces chunking/summarisation as the solution to long-input bloat. Chunking was considered and rejected — the real problem is editorial output length, not token limits.

### Retry on malformed output

If OpenAI returns structurally invalid JSON (rare with `response_format` strict mode), retry once. On second failure, set `status=failed` with a descriptive `error_message`.

### System prompt

Establishes Seek Sophie voice: warm, editorial, discerning. Not generic travel writing. Instructs the model to extract only what is in the notes, use direct quotes as `source_quote` values, omit `ethics_safety_notes` unless the notes contain explicit safety content, and write `best_for`/`not_for` as specific honest descriptors (not marketing copy).

---

## 6. Frontend — Pages

### `/` — Home

- Upload dropzone (drag-and-drop or file picker, `.docx` only)
- Client-side validation before upload: extension, file size
- On submit: `POST /articles`, navigate to `/articles/{id}`
- Article list below: title, filename, status badge, created date

### `/articles/[id]` — Article view + edit

**Processing state:**
- Skeleton layout with pulse animation
- Polls `/articles/{id}/status` every 2 seconds, up to 150 polls (5 minutes)
- On `failed`: stop polling, show error message, retry button
- On poll cap: show "Still processing — check back later" (does not mark as failed)
- On `completed`: fetch full article, render editable layout
- Retry resets the poll counter via a `retryKey` state increment that re-runs the `useEffect`

**Completed state — editorial layout:**

```
[ Title ]

[ Intro / Hook ]                       [source] or [unverified]

Section Heading
Section content...                     [source] or [unverified]

Best for              Not for
✓ Adventure seekers   ✗ Luxury travelers
  [source/unverified]   [source/unverified]

Ethics & Safety                        [source] or [unverified]
...

Key Facts
Label    Value                          [source] or [unverified]

[ View original notes ▾ ]
```

### Source attribution and unverified state

Every structured field renders one of two chips:
- `[source]` — interactive button, hover shows tooltip with verbatim quote from original notes
- `[unverified]` — amber static badge, indicates the LLM couldn't find a supporting quote

The amber state is visual only — no blocking, no dismiss action required. The editor's response is to open the original notes, verify the claim, and edit or accept it.

### Inline editing behaviour

- Controlled input toggle (not `contenteditable`)
- Click → `<textarea>` or `<input>` pre-filled with current value
- Blur or `Cmd+Enter` → fires `PATCH /articles/{id}`, reverts on failure
- Quiet "Saving…" / "Saved" indicator top-right

**Why not `contenteditable`:** Paste from Word injects raw HTML. Revert-on-error is complex. React cursor instability on re-render.

---

## 7. Error States

| Scenario | UI behaviour |
|----------|-------------|
| Upload non-docx | Client-side filter + server 422 error |
| Upload too large | Client-side check + 413 error |
| Corrupted docx | 422: "Could not read document" |
| Document too short | 422: word count + minimum shown |
| Daily limit reached | 429: "Try again tomorrow" |
| LLM timeout / failure | `status=failed`, error shown, retry button |
| Poll cap reached (5 min) | "Still processing — check back later" |
| PATCH fails on edit | Optimistic update reverts, error indicator on field |

---

## 8. Deployment

| Service | Platform |
|---------|----------|
| Next.js frontend | Vercel (free tier) |
| FastAPI backend + PostgreSQL | Railway (one service + Postgres plugin) |

Environment variables:
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `NEXT_PUBLIC_API_URL` (FastAPI base URL, set in Vercel)

---

## 9. What We Cut

| Cut | Reason |
|-----|--------|
| Auth / user accounts | Single-user internal tool. No multi-tenancy required at this scope. |
| Export to Word / PDF | Nice to have. Worth noting in writeup. |
| Edit history / versioning | `updated_at` tracks last save. Full versioning is a product decision beyond scope. |
| Image extraction from docx | `python-docx` supports it; article schema has no image field. Clean cut. |
| Streaming LLM output | Complicates structured output enforcement. Skeleton + polling gives adequate UX. |
| Celery / Redis | `BackgroundTasks` is sufficient for one instance. Writeup notes the scaling limitation. |
| Rich text in body | Plain text only. Editors write clean prose, not formatted HTML. |
| Chunking long documents | gpt-4o's 128k context window exceeds any realistic travel notes input. The real problem is editorial output length, not token limits — solved via prompt-level output caps instead. |
| Per-user generation limits | No auth = no user identity. Global daily cap (20/day) is sufficient to control cost. |
| Explicit verify action on unverified fields | Amber badge signals the issue; blocking or a dismiss button adds friction for no editorial benefit. |

---

## 10. Writeup

Points to make explicit in the submission:

- **Async choice:** Sync was rejected due to timeout risk on standard hosting and silent failure mode. Async + polling adds ~30 lines of frontend code and makes failure explicit and recoverable.
- **Structured output enforcement:** `response_format` with strict schema, not JSON mode — schema violations are caught at the API layer, not in post-processing.
- **Source attribution on every field:** Not just body sections. Every extracted claim — hook, best_for items, key facts, ethics — carries a `source_quote`. The unverified amber state makes gaps visible without blocking the editor.
- **Long document strategy:** Prompt-level output caps, not chunking. The editorial output should be tight regardless of input length. Chunking was considered and rejected as solving the wrong problem.
- **`contenteditable` rejection:** Paste behaviour, HTML injection, React cursor conflicts. Controlled toggle handles all three cleanly.
- **BackgroundTasks scaling limit:** Single-instance only. Production path is Celery + Redis.
- **Cost guardrails:** Short-doc check (< 50 words → 422 before any LLM call) and daily cap (20/day → 429) added as lightweight cost controls without auth infrastructure.
- **What was cut and why:** See section 9. Judgment calls are part of the evaluation.
