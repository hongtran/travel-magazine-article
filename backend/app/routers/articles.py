import asyncio
import uuid
from datetime import datetime, timezone, date
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI

from ..config import settings
from ..database import AsyncSessionLocal, get_db
from ..models import Article
from ..schemas import ArticleListItem, ArticleResponse, ArticleStatusResponse, ArticleUpdate
from ..services.document import DocumentError, extract_text
from ..services.llm import LLMError, LLMPermanentError, LLMTransientError, generate_article, validate_travel_relevance

router = APIRouter(prefix="/articles", tags=["articles"])

ALLOWED_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MIN_WORD_COUNT = 50
DAILY_GENERATION_LIMIT = 20

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


class _DocumentRejected(Exception):
    def __init__(self, reason: str):
        self.reason = reason


async def process_article(article_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            return
        try:
            client = get_openai_client()

            is_relevant, reason = await asyncio.wait_for(
                asyncio.to_thread(validate_travel_relevance, article.original_text, client),
                timeout=30.0,
            )
            if not is_relevant:
                raise _DocumentRejected(reason)

            result = await asyncio.wait_for(
                asyncio.to_thread(generate_article, article.original_text, client),
                timeout=120.0,
            )
            article.title = result["title"]
            article.intro_hook = result["intro_hook"]["content"]
            article.intro_hook_source_quote = result["intro_hook"]["source_quote"] or None
            article.body_sections = result["body_sections"]
            article.best_for = result["best_for"]
            article.not_for = result["not_for"]
            ethics = result["ethics_safety_notes"]
            if ethics:
                article.ethics_safety_notes = ethics["content"]
                article.ethics_safety_notes_source_quote = ethics["source_quote"] or None
            else:
                article.ethics_safety_notes = None
                article.ethics_safety_notes_source_quote = None
            article.key_facts = result["key_facts"]
            article.status = "completed"
        except _DocumentRejected as e:
            article.status = "rejected"
            article.error_message = f"This document doesn't appear to be about a travel experience. {e.reason}"
        except asyncio.TimeoutError:
            article.status = "failed"
            article.error_message = "Generation timed out. Please retry."
        except LLMPermanentError as e:
            article.status = "rejected"
            article.error_message = str(e)
        except (LLMTransientError, LLMError) as e:
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

    word_count = len(text.split())
    if word_count < MIN_WORD_COUNT:
        raise HTTPException(
            status_code=422,
            detail=f"Document is too short ({word_count} words). Please provide at least {MIN_WORD_COUNT} words of notes."
        )

    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    count_result = await db.execute(
        select(func.count()).where(Article.created_at >= today_start)
    )
    if count_result.scalar() >= DAILY_GENERATION_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Daily generation limit of {DAILY_GENERATION_LIMIT} articles reached. Try again tomorrow."
        )

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
    if article.status == "rejected":
        raise HTTPException(status_code=422, detail="This document was rejected and cannot be retried. Please upload travel experience notes.")
    if article.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed articles can be retried")

    article.status = "processing"
    article.error_message = None
    article.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(process_article, article.id)
    return ArticleStatusResponse(id=article.id, status="processing", error_message=None)
