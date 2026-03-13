import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers.webhook import router
from services.notion import ensure_uncategorized
from tasks import cleanup_expired_pending


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 기동 시 Uncategorized 프로젝트 보장 (실패해도 서버는 기동)
    try:
        await ensure_uncategorized()
    except Exception as e:
        print(f"[startup] ensure_uncategorized 실패 (무시): {e}")
    # 만료된 pending 정리 백그라운드 태스크 시작
    task = asyncio.create_task(cleanup_expired_pending())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Scribble", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
