import asyncpg
from fastapi import APIRouter, Depends, Response

from ..database import get_pool
from ..errors import APIError
from ..schemas import Cart, CartQuantity
from ..security import current_user
from ..services.cart import read_cart

router = APIRouter(prefix='/api/cart', tags=['Корзина'])


@router.get('', response_model=Cart)
async def cart(user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        return await read_cart(connection, user['id'])


@router.put('/items/{product_id}', response_model=Cart)
async def set_quantity(product_id: int, payload: CartQuantity, user: dict = Depends(current_user),
                       pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        row = await connection.fetchrow('SELECT * FROM store_products WHERE id=$1 FOR SHARE', product_id)
        if row is None or not row['is_active']:
            raise APIError(404, 'product_not_found', 'Товар не найден')
        if payload.quantity > row['quantity']:
            raise APIError(409, 'stock_conflict', 'Недостаточно товара на складе',
                           [{'product_id': product_id, 'requested': payload.quantity, 'available': row['quantity']}])
        count = await connection.fetchval('SELECT COUNT(*) FROM store_cart_items WHERE user_id=$1', user['id'])
        exists = await connection.fetchval('SELECT EXISTS(SELECT 1 FROM store_cart_items WHERE user_id=$1 AND product_id=$2)',
                                           user['id'], product_id)
        if count >= 100 and not exists:
            raise APIError(409, 'cart_limit', 'В корзине может быть не более 100 разных товаров')
        await connection.execute('''INSERT INTO store_cart_items(user_id,product_id,quantity) VALUES($1,$2,$3)
            ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=EXCLUDED.quantity''',
                                 user['id'], product_id, payload.quantity)
        return await read_cart(connection, user['id'])


@router.delete('/items/{product_id}', status_code=204, response_class=Response)
async def remove_item(product_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        await connection.execute('DELETE FROM store_cart_items WHERE user_id=$1 AND product_id=$2', user['id'], product_id)
    return Response(status_code=204)


@router.delete('', status_code=204, response_class=Response)
async def clear_cart(user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        await connection.execute('DELETE FROM store_cart_items WHERE user_id=$1', user['id'])
    return Response(status_code=204)
