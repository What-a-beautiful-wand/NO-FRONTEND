import re
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = "postgresql://postgres:Pg18_550655535df24b9081d663ebbfa7b85dAa7@localhost:5432/postgres"

class ProductInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    group_name: str = Field(min_length=1, max_length=200)
    price: int = Field(gt=0)
    img_href: str = Field(min_length=1, max_length=2000)
    year: int = Field(gt=0, le=2100)
    duration: str = Field(pattern=r"^[0-9]+:[0-5][0-9]$")
    quantity: int = Field(gt=0)

    @field_validator("title", "group_name")
    @classmethod
    def trim_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не должно быть пустым")
        return value

    @field_validator("img_href")
    @classmethod
    def require_http_image_url(cls, value: str) -> str:
        value = value.strip()
        if not re.match(r"^https?://", value, re.IGNORECASE):
            raise ValueError("Ссылка на обложку должна начинаться с http:// или https://")
        return value


class ContactInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    tel: str = Field(default="", max_length=40)
    problem_text: str = Field(min_length=1, max_length=10000)

    @field_validator("email", "tel", "problem_text")
    @classmethod
    def trim_values(cls, value: str) -> str:
        return value.strip()


def serialize_product(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "group_name": row["group_name"],
        "price": row["price"],
        "img_name": row["img_name"],
        "img_href": row["img_href"],
        "like": row["is_favorite"],
        "year": row["year"],
        "duration": row["duration"],
        "quantity": row["quantity"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with app.state.db_pool.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS store_products (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                group_name TEXT NOT NULL,
                price INTEGER NOT NULL CHECK (price > 0),
                img_name TEXT NOT NULL,
                img_href TEXT NOT NULL,
                is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
                year INTEGER NOT NULL CHECK (year > 0),
                duration TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            )
        """)
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS store_messages (
                id BIGSERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                tel TEXT NOT NULL DEFAULT '',
                problem_text TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    try:
        yield
    finally:
        await app.state.db_pool.close()


app = FastAPI(title="Магазин виниловых пластинок", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/main.css", include_in_schema=False)
async def stylesheet():
    return FileResponse(BASE_DIR / "main.css", media_type="text/css", headers={"Cache-Control": "no-store"})


@app.get("/script.js", include_in_schema=False)
async def javascript():
    return FileResponse(BASE_DIR / "script.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/health")
async def health(request: Request):
    try:
        async with request.app.state.db_pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
    except (asyncpg.PostgresError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "connected"}


@app.get("/api/products")
async def list_products(request: Request):
    async with request.app.state.db_pool.acquire() as connection:
        rows = await connection.fetch("SELECT * FROM store_products ORDER BY id")
    return [serialize_product(row) for row in rows]


@app.post("/api/products", status_code=201)
async def create_product(product: ProductInput, request: Request):
    async with request.app.state.db_pool.acquire() as connection:
        row = await connection.fetchrow("""
            INSERT INTO store_products
                (title, group_name, price, img_name, img_href, year, duration, quantity)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
        """, product.title, product.group_name, product.price,
            f"Обложка альбома {product.title}", product.img_href, product.year,
            product.duration, product.quantity)
    return serialize_product(row)


@app.patch("/api/products/{product_id}/favorite")
async def toggle_favorite(product_id: int, request: Request):
    async with request.app.state.db_pool.acquire() as connection:
        row = await connection.fetchrow("""
            UPDATE store_products SET is_favorite = NOT is_favorite
            WHERE id = $1 RETURNING *
        """, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return serialize_product(row)


@app.delete("/api/products/{product_id}", status_code=204)
async def delete_product(product_id: int, request: Request):
    async with request.app.state.db_pool.acquire() as connection:
        result = await connection.execute("DELETE FROM store_products WHERE id = $1", product_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Товар не найден")


@app.post("/api/messages", status_code=201)
async def create_message(message: ContactInput, request: Request):
    if not message.email or not message.problem_text:
        raise HTTPException(status_code=422, detail="Укажите почту и описание проблемы")
    async with request.app.state.db_pool.acquire() as connection:
        message_id = await connection.fetchval("""
            INSERT INTO store_messages (email, tel, problem_text)
            VALUES ($1, $2, $3) RETURNING id
        """, message.email, message.tel, message.problem_text)
    return {"id": message_id, "status": "received"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
