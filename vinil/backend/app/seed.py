"""Normalize the user's JSON catalog without modifying its source or existing DB."""
import json
from pathlib import Path

import asyncpg
from .config import BASE_DIR
from .schemas import ProductInput

SEED_NAME = 'vinyl-catalog-v1'


def load_mock_products() -> list[dict]:
    products = json.loads((BASE_DIR / 'mocks' / 'products.json').read_text(encoding='utf-8'))
    result = []
    for source in products:
        item = dict(source)
        href = item['img_href']
        if href.startswith('/mocks/media/'):
            media = BASE_DIR / 'mocks' / 'media'
            filename = Path(href).name
            if filename == 'trench-yop.jpg':
                filename = 'trench-top.jpg'
            if not (media / filename).is_file():
                matches = [p for p in media.iterdir() if p.stem.casefold() == Path(filename).stem.casefold()]
                if len(matches) == 1:
                    filename = matches[0].name
            item['img_href'] = f'/mocks/media/{filename}'
        item.setdefault('img_name', f"Обложка альбома {item['title']}")
        # Old shared "like" values have no account owner and are not imported into personal favorites.
        item.pop('like', None)
        values = ProductInput.model_validate({k: v for k, v in item.items() if k != 'img_name'})
        result.append(values.model_dump() | {'img_name': item['img_name']})
    return result


async def seed_products(connection: asyncpg.Connection) -> bool:
    async with connection.transaction():
        await connection.execute('SELECT pg_advisory_xact_lock(7401001)')
        if await connection.fetchval('SELECT EXISTS (SELECT 1 FROM store_seed_history WHERE name = $1)', SEED_NAME):
            return False
        if not await connection.fetchval('SELECT EXISTS (SELECT 1 FROM store_products)'):
            for item in load_mock_products():
                columns = list(item)
                placeholders = ','.join(f'${i}' for i in range(1, len(columns) + 1))
                await connection.execute(
                    f"INSERT INTO store_products ({','.join(columns)}) VALUES ({placeholders})", *item.values())
        await connection.execute('INSERT INTO store_seed_history(name) VALUES($1)', SEED_NAME)
        return True
