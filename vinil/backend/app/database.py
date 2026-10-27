"""Database pool and schema initialization."""

from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request

from .config import BASE_DIR, Settings
from .seed import seed_products


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    app.state.db_pool = pool
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(7401000)")
                await connection.execute((BASE_DIR / "sql" / "schema.sql").read_text(encoding="utf-8"))
            if settings.seed_mock_data:
                await seed_products(connection)
        yield
    finally:
        await pool.close()
