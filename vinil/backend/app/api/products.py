"""Catalog operations; field names remain compatible with the original API."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response

from ..database import get_pool
from ..schemas import Product, ProductInput

router = APIRouter(prefix="/api/products", tags=["Каталог"])


def serialize_product(row: asyncpg.Record) -> dict:
    product = dict(row)
    product["like"] = product.pop("is_favorite")
    return product


@router.get("", response_model=list[Product])
async def list_products(pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        rows = await connection.fetch("SELECT * FROM store_products ORDER BY id")
    return [serialize_product(row) for row in rows]


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow("SELECT * FROM store_products WHERE id = $1", product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return serialize_product(row)


@router.post("", status_code=201, response_model=Product)
async def create_product(product: ProductInput, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO store_products
                (title, group_name, price, img_name, img_href, year, duration, quantity)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *
            """,
            product.title, product.group_name, product.price,
            f"Обложка альбома {product.title}", product.img_href,
            product.year, product.duration, product.quantity,
        )
    return serialize_product(row)


@router.patch("/{product_id}/favorite", response_model=Product)
async def toggle_favorite(product_id: int, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """UPDATE store_products SET is_favorite = NOT is_favorite
            WHERE id = $1 RETURNING *""", product_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return serialize_product(row)


@router.delete("/{product_id}", status_code=204, response_class=Response)
async def delete_product(product_id: int, pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        result = await connection.execute("DELETE FROM store_products WHERE id = $1", product_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Товар не найден")
    return Response(status_code=204)
