"""Load demo products once, without replacing existing store data."""

import json

import asyncpg

from .config import BASE_DIR
from .schemas import ProductInput

SEED_NAME = "vinyl-catalog-v1"


def load_mock_products() -> list[dict]:
    products = json.loads((BASE_DIR / "mocks" / "products.json").read_text(encoding="utf-8"))
    for product in products:
        ProductInput.model_validate(product)
    return products


async def seed_products(connection: asyncpg.Connection) -> bool:
    async with connection.transaction():
        # Serialize initialization across workers using the same database.
        await connection.execute("SELECT pg_advisory_xact_lock(7401001)")
        if await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM store_seed_history WHERE name = $1)", SEED_NAME
        ):
            return False
        # An existing catalog belongs to the user; leave it untouched.
        if not await connection.fetchval("SELECT EXISTS (SELECT 1 FROM store_products)"):
            products = load_mock_products()
            await connection.executemany(
                """
                INSERT INTO store_products
                    (title, group_name, price, img_name, img_href, is_favorite, year, duration, quantity)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                [
                    (
                        item["title"], item["group_name"], item["price"],
                        item["img_name"], item["img_href"], item["like"],
                        item["year"], item["duration"], item["quantity"],
                    )
                    for item in products
                ],
            )
        await connection.execute("INSERT INTO store_seed_history (name) VALUES ($1)", SEED_NAME)
        return True
