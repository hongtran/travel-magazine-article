import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .database import engine, Base, AsyncSessionLocal
from .models import Article
from .routers import articles

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Article).where(Article.status == "processing"))
        stuck = result.scalars().all()
        for article in stuck:
            article.status = "failed"
            article.error_message = "Server restarted during generation. Please retry."
        if stuck:
            await db.commit()

    yield

app = FastAPI(title="Travel Magazine Article Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.environ.get("FRONTEND_URL", ""),
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
