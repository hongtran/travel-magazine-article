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
2. FastAPI validates file, extracts text, creates article record with `status=processing`, fires `BackgroundTask`, returns `{id, status}` immediately
3. Background task: parse → OpenAI call → DB update to `status=completed` or `status=failed`
4. Frontend navigates to `/articles/{id}`, polls `/articles/{id}/status` every 2 seconds
5. On `completed`: fetch full article, render editable layout. On `failed`: show error + retry button.

**Why async over sync:** OpenAI calls take 10–30 seconds. Standard hosting platforms (Railway, Render) have HTTP timeout limits around 30–60 seconds. Sync risks silent timeout failures where the result is lost. Async makes the failure surface explicit and recoverable. Trade-off: requires polling logic (~30 lines of frontend code) and a status field on the article record.

**Scaling note:** FastAPI `BackgroundTasks` runs in-process — adequate for a single instance. Production horizontal scaling would require an external queue (Celery + Redis or similar). Worth flagging in the writeup.

---

## 3. Data Model

One table. Structured fields in JSONB for flexibility without migrations.

```sql
CREATE TABLE articles (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  status               TEXT NOT NULL DEFAULT 'processing',
                       -- 'processing' | 'completed' | 'failed'
  original_filename    TEXT NOT NULL,
  original_text        TEXT NOT NULL,
  title                TEXT,
  intro_hook           TEXT,
  body_sections        JSONB,
  best_for             JSONB,
  not_for              JSONB,
  ethics_safety_notes  TEXT,
  key_facts            JSONB,
  error_message        TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
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

// best_for / not_for
["Adventure seekers", "Solo travellers", "Nature photographers"]
```

### Design decisions

- `original_text` is stored permanently. Source quotes are only verifiable against the stored raw text — without it, citations are unverifiable.
- `source_quote` lives at the item level (per section, per fact), not at the article level. A broad article-level citation is useless for verification.
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
- Extracted text is non-empty (catches blank documents)

Returns `{id, status: "processing"}` immediately. Frontend navigates and starts polling.

### GET /articles/{id}/status

Returns only `{id, status, error_message}`. Keeps the polling loop lightweight — not re-fetching full JSONB on every tick. Frontend does one full `GET /articles/{id}` when status reaches `completed`.

### PATCH /articles/{id}

Partial update — only fields included in the request body are updated. Inline editing sends one field at a time. Updates `updated_at`. Returns the updated article.

```json
// example
{ "intro_hook": "The boat smells like diesel and possibility..." }
```

### Error responses

| Scenario | Status | Message |
|----------|--------|---------|
| Non-docx file | 422 | `"Only .docx files are supported"` |
| File too large | 413 | `"File must be under 10MB"` |
| Corrupted docx | 422 | `"Could not read document — is it a valid .docx?"` |
| Blank document | 422 | `"Document appears to be empty"` |
| Article not found | 404 | `"Article not found"` |
| OpenAI timeout / bad JSON | stored as `status=failed` | surfaced via `/status` poll |

OpenAI failures do not return 5xx — the upload succeeded. The failure surfaces through the poll as `status=failed` with `error_message`. The frontend offers a retry button that calls `POST /articles/{id}/retry`, which resets status to `processing` and re-fires the background task using the stored `original_text` — no re-upload needed.

---

## 5. LLM Integration

### Structured output schema

OpenAI call uses `response_format` with a strict JSON schema. This enforces structure at the API level — not prose with a schema sprinkled on top.

```python
ARTICLE_SCHEMA = {
  "type": "object",
  "required": ["title", "intro_hook", "body_sections", "best_for", "not_for", "key_facts"],
  "properties": {
    "title": {"type": "string"},
    "intro_hook": {"type": "string"},
    "body_sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["heading", "content", "source_quote"],
        "properties": {
          "heading": {"type": "string"},
          "content": {"type": "string"},
          "source_quote": {"type": "string"}
        }
      }
    },
    "best_for": {"type": "array", "items": {"type": "string"}},
    "not_for": {"type": "array", "items": {"type": "string"}},
    "ethics_safety_notes": {"type": ["string", "null"]},
    "key_facts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["label", "value", "source_quote"],
        "properties": {
          "label": {"type": "string"},
          "value": {"type": "string"},
          "source_quote": {"type": "string"}
        }
      }
    }
  }
}
```

### Hallucination mitigation

`source_quote` is a required field on every body section and key fact. The LLM must cite the verbatim sentence from the original notes that supports each claim. If no supporting text exists in the notes, the LLM cannot fabricate a plausible quote — the absence itself signals a hallucination risk. Editors see these source chips in the UI and can verify instantly.

This is not a guarantee — it is a forcing function that makes unsupported claims visible rather than hiding them in fluent prose.

### Retry on malformed output

If OpenAI returns structurally invalid JSON (rare with `response_format` strict mode), retry once. On second failure, set `status=failed` with a descriptive `error_message`.

### System prompt

Establishes Seek Sophie voice: warm, editorial, discerning. Not generic travel writing. Instructs the model to:
- Extract only what is present in the notes — do not embellish
- Use direct quotes from the original as `source_quote` values
- Omit `ethics_safety_notes` if nothing in the notes warrants it
- Write `best_for` and `not_for` as specific, honest descriptors (not marketing copy)

---

## 6. Frontend — Pages

### `/` — Home

- Upload dropzone (drag-and-drop or file picker, `.docx` only)
- Client-side validation before upload: extension, file size
- On submit: `POST /articles`, navigate to `/articles/{id}`
- Article list below: title, filename, status badge, created date
- `status=failed` rows show a warning indicator

### `/articles/[id]` — Article view + edit

**Processing state** (while `status=processing`):
- Skeleton layout with spinner
- Polls `/articles/{id}/status` every 2 seconds
- On `failed`: stop polling, show error message, retry button
- On `completed`: fetch full article, render editable layout

**Completed state** — editorial layout:

```
[ Title ]                              ← <input>, click to edit

[ Intro / Hook ]                       ← <textarea>, click to edit

Getting There                          ← heading editable
The boat departs from Labuan Bajo...   ← content editable
                                         [source] chip → tooltip with original quote

What to Expect
...

Best for              Not for
────────              ───────
✓ Adventure seekers   ✗ Families with young children
✓ Solo travellers     ✗ Those with mobility issues
  [+ add]               [+ add]        ← each tag editable/deletable/addable

Ethics & Safety                        ← only rendered if non-empty
...

Key Facts
──────────────────────────────────
Price      SGD 180–220/person  [source]
Duration   3 days              [source]
Season     Apr–Oct             [source]
[+ add fact]

[ View original notes ▾ ]              ← toggle, shows full raw extracted text
```

### Inline editing behaviour

- Implementation: **controlled input toggle** (not `contenteditable`)
- Display mode: styled HTML (`<h2>`, `<p>`, etc.)
- Click → swaps to controlled `<textarea>` or `<input>` pre-filled with current value
- Blur or `Cmd+Enter` → swaps back to display, fires `PATCH /articles/{id}`
- Optimistic update: UI reflects edit immediately, reverts on PATCH failure
- Quiet "Saving..." / "Saved" indicator top-right — not a toast on every blur

**Why controlled toggle over `contenteditable`:** Paste from Word/Google Docs into `contenteditable` injects raw HTML that corrupts stored values. Controlled textarea handles paste as plain text. Reverting on PATCH failure is one line (reset state). React + `contenteditable` has known cursor-position conflicts on re-render.

### Source attribution

`[source]` chip on each body section and key fact. Hover shows tooltip with the verbatim `source_quote` from the original notes. Makes hallucinations visible without requiring the editor to open the full original.

"View original notes" toggle below the article renders the full `original_text`. Covers verification cases the source chips don't surface.

---

## 7. Error States

| Scenario | UI behaviour |
|----------|-------------|
| Upload non-docx | Client-side: file picker filters. Server-side: 422 toast error |
| Upload too large | Client-side check + 413 toast error |
| Corrupted docx | 422 toast: "Could not read document" |
| Blank document | 422 toast: "Document appears to be empty" |
| LLM timeout / failure | status=failed, error message shown, retry button |
| PATCH fails on edit | Optimistic update reverts, brief error indicator on field |
| User navigates away while editing | Browser `beforeunload` warning if unsaved edit in progress |

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

## 9. What We're Cutting

Explicit trade-offs made for the 4-hour constraint:

| Cut | Reason |
|-----|--------|
| Auth / user accounts | Single-user internal tool. No multi-tenancy required at this scope. |
| Export to Word / PDF | Nice to have. Worth noting in writeup. |
| Edit history / versioning | `updated_at` tracks last save. Full versioning is a product decision beyond this scope. |
| Image extraction from docx | `python-docx` supports it; the article schema doesn't have an image field. Clean cut. |
| Streaming LLM output | Complicates structured output enforcement. Skeleton + polling gives adequate UX. |
| Celery / Redis | `BackgroundTasks` is sufficient for one instance. Writeup notes the scaling limitation. |
| Rich text formatting in body | Plain text fields only. Editors write clean prose, not formatted HTML. |

---

## 10. What the Writeup Should Surface

Points to make explicit in the submission writeup (not just in the code):

- **Async choice:** Why sync was rejected — timeout risk on standard hosting, silent failure mode.
- **Structured output enforcement:** `response_format` with strict schema, not JSON mode — schema violations are caught at the API layer.
- **Hallucination approach:** `source_quote` as a forcing function, not a guarantee. Makes unsupported claims visible.
- **`contenteditable` rejection:** Paste behaviour, HTML injection, React cursor conflicts.
- **BackgroundTasks scaling limit:** Single-instance only. Production path is Celery + Redis.
- **What was cut and why:** See section 9. Judgment calls are part of the evaluation.
