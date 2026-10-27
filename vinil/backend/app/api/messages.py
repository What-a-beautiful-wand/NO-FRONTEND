import asyncpg
from fastapi import APIRouter, Depends

from ..database import get_pool
from ..schemas import ContactInput

router = APIRouter(prefix="/api/messages", tags=["Обратная связь"])


@router.post("", status_code=201)
async def create_message(message: ContactInput, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        message_id = await connection.fetchval(
            """INSERT INTO store_messages (email, tel, problem_text)
            VALUES ($1, $2, $3) RETURNING id""",
            message.email, message.tel, message.problem_text,
        )
    return {"id": message_id, "status": "received"}
