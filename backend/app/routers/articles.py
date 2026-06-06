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
