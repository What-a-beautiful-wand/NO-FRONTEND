"""Transactional, versioned startup migrations and PostgreSQL pool."""
from contextlib import asynccontextmanager
import hashlib

import asyncpg
from fastapi import FastAPI, Request

from .config import BASE_DIR, Settings
from .seed import seed_products


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


async def migrate(connection: asyncpg.Connection):
    async with connection.transaction():
        await connection.execute('SELECT pg_advisory_xact_lock(7401000)')
        await connection.execute('''CREATE TABLE IF NOT EXISTS store_schema_migrations (
            version TEXT PRIMARY KEY, checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        for path in sorted((BASE_DIR / 'sql' / 'migrations').glob('*.sql')):
            source = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(source.encode()).hexdigest()
            applied = await connection.fetchval(
                'SELECT checksum FROM store_schema_migrations WHERE version = $1', path.name)
            if applied is not None:
                if applied != checksum:
                    raise RuntimeError(f'Applied migration changed: {path.name}')
                continue
            await connection.execute(source)
            await connection.execute('INSERT INTO store_schema_migrations(version, checksum) VALUES($1,$2)',
                                     path.name, checksum)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    settings.media_root.mkdir(parents=True, exist_ok=True)
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10,
                                    command_timeout=30)
    app.state.db_pool = pool
    try:
        async with pool.acquire() as connection:
            await migrate(connection)
            if settings.seed_mock_data:
                await seed_products(connection)
            await connection.execute('DELETE FROM store_sessions WHERE expires_at < NOW()')
            await connection.execute("DELETE FROM store_login_attempts WHERE window_started < NOW() - INTERVAL '1 day'")
        yield
    finally:
        await pool.close()
