import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_pool

router = APIRouter(tags=["Состояние"])


@router.get("/health")
async def health(pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
    except (asyncpg.PostgresError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}
