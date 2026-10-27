import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from ..database import get_pool
from ..errors import APIError
from ..schemas import Page, Product
from ..security import current_user
from ..services.catalog import PRODUCT_SELECT, find_product, page_result, product_dict

router = APIRouter(prefix='/api/favorites', tags=['Избранное'])


@router.get('', response_model=Page[Product])
async def favorites(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                    user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        total = await connection.fetchval('''SELECT COUNT(*) FROM store_favorites f JOIN store_products p
            ON p.id=f.product_id WHERE f.user_id=$1 AND p.is_active''', user['id'])
        rows = await connection.fetch(PRODUCT_SELECT + ''' WHERE p.is_active AND EXISTS(
            SELECT 1 FROM store_favorites f WHERE f.user_id=$1 AND f.product_id=p.id)
            ORDER BY p.id DESC LIMIT $2 OFFSET $3''', user['id'], per_page, (page-1)*per_page)
    return page_result([product_dict(row) for row in rows], total, page, per_page)


@router.put('/{product_id}', response_model=Product)
async def add_favorite(product_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        product = await find_product(connection, product_id, user['id'])
        if product is None or not product['is_active']:
            raise APIError(404, 'product_not_found', 'Товар не найден')
        await connection.execute('INSERT INTO store_favorites(user_id,product_id) VALUES($1,$2) ON CONFLICT DO NOTHING',
                                 user['id'], product_id)
        return product_dict(await find_product(connection, product_id, user['id']))


@router.delete('/{product_id}', status_code=204, response_class=Response)
async def remove_favorite(product_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        await connection.execute('DELETE FROM store_favorites WHERE user_id=$1 AND product_id=$2', user['id'], product_id)
    return Response(status_code=204)
