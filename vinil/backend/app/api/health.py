import asyncpg
from fastapi import APIRouter, Depends
from ..database import get_pool
from ..errors import APIError

router = APIRouter(tags=['Состояние'])


@router.get('/health')
async def health(pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as connection:
            await connection.fetchval('SELECT 1')
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        raise APIError(503, 'database_unavailable', 'База данных недоступна') from exc
    return {'status': 'ok', 'database': 'connected'}
