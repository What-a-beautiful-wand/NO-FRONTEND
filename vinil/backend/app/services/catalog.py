import math

import asyncpg
from ..schemas import Product

PRODUCT_SELECT = '''SELECT p.*, EXISTS(SELECT 1 FROM store_favorites f
    WHERE f.product_id=p.id AND f.user_id=$1) AS "like" FROM store_products p'''


def product_dict(row) -> dict:
    return Product.model_validate(dict(row)).model_dump()


def page_result(items, total, page, per_page):
    return {'items': items, 'total': total, 'page': page, 'per_page': per_page,
            'pages': math.ceil(total / per_page)}


async def find_product(connection: asyncpg.Connection, product_id: int, user_id: int | None = None):
    return await connection.fetchrow(PRODUCT_SELECT + ' WHERE p.id=$2', user_id, product_id)
