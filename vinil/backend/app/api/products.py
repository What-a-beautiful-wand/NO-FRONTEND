from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from ..database import get_pool
from ..errors import APIError
from ..schemas import CatalogFilters, Page, Product, ProductInput
from ..security import admin_user, current_user, optional_user
from ..services.catalog import PRODUCT_SELECT, find_product, page_result, product_dict

router = APIRouter(prefix='/api/products', tags=['Каталог'])


@router.get('', response_model=Page[Product])
async def list_products(
    q: str = Query('', max_length=200), genre: str | None = Query(None, max_length=200),
    artist: str | None = Query(None, max_length=200),
    format: Literal['LP', '2LP', 'EP', 'Single'] | None = None,
    condition: Literal['new', 'used'] | None = None,
    year_min: int | None = Query(None, ge=1, le=2100), year_max: int | None = Query(None, ge=1, le=2100),
    price_min: int | None = Query(None, ge=0), price_max: int | None = Query(None, ge=0),
    in_stock: bool = False, include_inactive: bool = False,
    sort: Literal['newest', 'price_asc', 'price_desc', 'title', 'year_desc'] = 'newest',
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    user: dict | None = Depends(optional_user), pool: asyncpg.Pool = Depends(get_pool),
):
    if include_inactive and (not user or user['role'] != 'admin'):
        raise APIError(403, 'forbidden', 'Скрытые товары доступны администратору')
    if (price_min is not None and price_max is not None and price_min > price_max) or (
            year_min is not None and year_max is not None and year_min > year_max):
        raise APIError(422, 'invalid_range', 'Начало диапазона больше конца')
    values = [user['id'] if user else None]
    conditions = ['TRUE' if include_inactive else 'p.is_active']
    def add(template, value):
        values.append(value)
        conditions.append(template.format(n=len(values)))
    if q.strip():
        # Treat SQL wildcard characters as literal search text.
        search = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        add("(p.title ILIKE ${n} OR p.group_name ILIKE ${n})", f'%{search}%')
    for column, value in [('genre', genre), ('group_name', artist), ('format', format), ('condition', condition)]:
        if value is not None:
            add(f'lower(p.{column}) = lower(${{n}})', value.strip())
    for column, operator, value in [('year', '>=', year_min), ('year', '<=', year_max),
                                    ('price', '>=', price_min), ('price', '<=', price_max)]:
        if value is not None:
            add(f'p.{column} {operator} ${{n}}', value)
    if in_stock:
        conditions.append('p.quantity > 0')
    where = ' WHERE ' + ' AND '.join(conditions)
    ordering = {'newest': 'p.id DESC', 'price_asc': 'p.price, p.id', 'price_desc': 'p.price DESC, p.id',
                'title': 'p.title, p.id', 'year_desc': 'p.year DESC, p.id'}[sort]
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        # Keep $1 reserved for the optional current account even in the count query.
        total = await connection.fetchval('SELECT COUNT(*) FROM store_products p' + where +
                                          ' AND ($1::bigint IS NULL OR $1::bigint IS NOT NULL)', *values)
        rows = await connection.fetch(PRODUCT_SELECT + where + f' ORDER BY {ordering}' +
                                      f' LIMIT ${len(values)+1} OFFSET ${len(values)+2}',
                                      *values, per_page, (page - 1) * per_page)
    return page_result([product_dict(row) for row in rows], total, page, per_page)


@router.get('/filters', response_model=CatalogFilters)
async def filters(pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow('''SELECT
            array_agg(DISTINCT genre ORDER BY genre) AS genres,
            array_agg(DISTINCT group_name ORDER BY group_name) AS artists,
            array_agg(DISTINCT format ORDER BY format) AS formats,
            MIN(price) AS price_min, MAX(price) AS price_max,
            MIN(year) AS year_min, MAX(year) AS year_max
            FROM store_products WHERE is_active''')
    return dict(row) | {key: row[key] or [] for key in ('genres', 'artists', 'formats')}


@router.get('/{product_id}', response_model=Product)
async def get_product(product_id: int, user: dict | None = Depends(optional_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await find_product(connection, product_id, user['id'] if user else None)
    if row is None or (not row['is_active'] and (not user or user['role'] != 'admin')):
        raise APIError(404, 'product_not_found', 'Товар не найден')
    return product_dict(row)


@router.post('', status_code=201, response_model=Product)
async def create_product(payload: ProductInput, user: dict = Depends(admin_user), pool: asyncpg.Pool = Depends(get_pool)):
    data = payload.model_dump() | {'img_name': f'Обложка альбома {payload.title}'}
    columns = list(data)
    async with pool.acquire() as connection:
        row = await connection.fetchrow(f"INSERT INTO store_products({','.join(columns)}) VALUES(" +
                                        ','.join(f'${i}' for i in range(1, len(columns)+1)) + ') RETURNING id',
                                        *data.values())
        return product_dict(await find_product(connection, row['id'], user['id']))


@router.put('/{product_id}', response_model=Product)
async def update_product(product_id: int, payload: ProductInput, user: dict = Depends(admin_user),
                         pool: asyncpg.Pool = Depends(get_pool)):
    data = payload.model_dump() | {'img_name': f'Обложка альбома {payload.title}'}
    assignments = ','.join(f'{column}=${i}' for i, column in enumerate(data, 1))
    async with pool.acquire() as connection:
        row = await connection.fetchrow(f'UPDATE store_products SET {assignments},updated_at=NOW() '
                                        f'WHERE id=${len(data)+1} RETURNING id', *data.values(), product_id)
        if row is None:
            raise APIError(404, 'product_not_found', 'Товар не найден')
        return product_dict(await find_product(connection, product_id, user['id']))


@router.delete('/{product_id}', status_code=204, response_class=Response)
async def delete_product(product_id: int, user: dict = Depends(admin_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        result = await connection.execute('UPDATE store_products SET is_active=FALSE,updated_at=NOW() WHERE id=$1', product_id)
    if result == 'UPDATE 0':
        raise APIError(404, 'product_not_found', 'Товар не найден')
    return Response(status_code=204)


@router.patch('/{product_id}/favorite', response_model=Product, deprecated=True)
async def toggle_favorite(product_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        product = await find_product(connection, product_id, user['id'])
        if product is None or not product['is_active']:
            raise APIError(404, 'product_not_found', 'Товар не найден')
        if product['like']:
            await connection.execute('DELETE FROM store_favorites WHERE user_id=$1 AND product_id=$2', user['id'], product_id)
        else:
            await connection.execute('INSERT INTO store_favorites(user_id,product_id) VALUES($1,$2)', user['id'], product_id)
        return product_dict(await find_product(connection, product_id, user['id']))
