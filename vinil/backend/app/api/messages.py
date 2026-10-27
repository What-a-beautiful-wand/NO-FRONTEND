import asyncpg
from fastapi import APIRouter, Depends

from ..database import get_pool
from ..schemas import ContactInput, MessageReceipt

router = APIRouter(prefix='/api/messages', tags=['Обратная связь'])


@router.post('', status_code=201, response_model=MessageReceipt)
async def create_message(message: ContactInput, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow('''INSERT INTO store_messages(email,tel,problem_text)
            VALUES($1,$2,$3) RETURNING id,created_at''', str(message.email).lower(), message.tel, message.problem_text)
    return dict(row) | {'status': 'received'}
