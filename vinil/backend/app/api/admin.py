import asyncio
from io import BytesIO
from uuid import uuid4
import warnings

import asyncpg
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError

from ..database import get_pool
from ..errors import APIError
from ..schemas import Message, MessageStatusInput, Order, OrderStatus, OrderStatusInput, Page, UploadResponse
from ..security import admin_user
from ..services.catalog import page_result
from ..services.orders import change_status, get_order, order_documents

router = APIRouter(prefix='/api/admin', tags=['Администрирование'], dependencies=[Depends(admin_user)])


@router.get('/orders', response_model=Page[Order])
async def all_orders(status: OrderStatus | None = None, page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                     pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        total = await connection.fetchval('SELECT COUNT(*) FROM store_orders WHERE ($1::text IS NULL OR status=$1)', status)
        rows = await connection.fetch('''SELECT * FROM store_orders WHERE ($1::text IS NULL OR status=$1)
            ORDER BY id DESC LIMIT $2 OFFSET $3''', status, per_page, (page-1)*per_page)
        return page_result(await order_documents(connection, rows), total, page, per_page)


@router.get('/orders/{order_id}', response_model=Order)
async def admin_order(order_id: int, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        return await get_order(connection, order_id)


@router.patch('/orders/{order_id}/status', response_model=Order)
async def order_status(order_id: int, payload: OrderStatusInput, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        return await change_status(connection, order_id, payload.status)


@router.get('/messages', response_model=Page[Message])
async def messages(status: str | None = Query(None, pattern=r'^(open|resolved)$'),
                   page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                   pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        total = await connection.fetchval('SELECT COUNT(*) FROM store_messages WHERE ($1::text IS NULL OR status=$1)', status)
        rows = await connection.fetch('''SELECT * FROM store_messages WHERE ($1::text IS NULL OR status=$1)
            ORDER BY id DESC LIMIT $2 OFFSET $3''', status, per_page, (page-1)*per_page)
        return page_result([dict(row) for row in rows], total, page, per_page)


@router.patch('/messages/{message_id}', response_model=Message)
async def message_status(message_id: int, payload: MessageStatusInput, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow('UPDATE store_messages SET status=$1 WHERE id=$2 RETURNING *', payload.status, message_id)
        if row is None:
            raise APIError(404, 'message_not_found', 'Обращение не найдено')
        return dict(row)


def store_image(data: bytes, directory):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 16000000:
                    raise APIError(422, 'invalid_image', 'Нужен JPEG, PNG или WebP размером до 16 мегапикселей')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                clean = image.convert('RGBA')
                clean.info.clear()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise APIError(422, 'invalid_image', 'Не удалось прочитать изображение') from exc
    filename = f'{uuid4().hex}.png'
    temporary = directory / f'{filename}.tmp'
    width, height = clean.size
    try:
        with temporary.open('xb') as output:
            clean.save(output, format='PNG')
        temporary.replace(directory / filename)
    finally:
        clean.close()
        temporary.unlink(missing_ok=True)
    return {'img_href': f'/media/uploads/{filename}', 'width': width, 'height': height}


@router.post('/media', status_code=201, response_model=UploadResponse)
async def upload_media(request: Request, file: UploadFile = File(...)):
    try:
        data = await file.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024:
            raise APIError(413, 'file_too_large', 'Максимальный размер обложки — 5 МиБ')
        return await asyncio.to_thread(store_image, data, request.app.state.settings.media_root)
    finally:
        await file.close()
