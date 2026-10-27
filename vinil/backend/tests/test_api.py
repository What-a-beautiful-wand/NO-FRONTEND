"""Integration tests use disposable PostgreSQL schemas, never the store tables."""

import asyncio
import os
from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import load_mock_products


def test_mock_catalog():
    products = load_mock_products()
    assert len(products) == 12
    assert len({(item["title"], item["group_name"]) for item in products}) == 12
    assert any(item["quantity"] == 0 for item in products)
    from app.config import BASE_DIR

    for item in products:
        assert (BASE_DIR / "static" / item["img_href"].removeprefix("/media/")).is_file()


@pytest.fixture
def settings():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    schema = f"vinil_test_{uuid4().hex}"

    async def create_schema():
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(f'CREATE SCHEMA "{schema}"')
        finally:
            await connection.close()

    async def drop_schema():
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await connection.close()

    asyncio.run(create_schema())
    url = urlsplit(database_url)
    query = dict(parse_qsl(url.query))
    query["search_path"] = schema
    isolated_url = urlunsplit(url._replace(query=urlencode(query)))
    try:
        yield Settings(isolated_url, True, ("http://localhost:5173",))
    finally:
        asyncio.run(drop_schema())


def test_catalog_and_restart(settings):
    with TestClient(create_app(settings)) as client:
        products = client.get("/api/products").json()
        assert len(products) == 12
        assert client.delete(f'/api/products/{products[0]["id"]}').status_code == 204
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/api/products").json()) == 11


def test_product_lifecycle(settings):
    with TestClient(create_app(settings)) as client:
        payload = {key: value for key, value in load_mock_products()[0].items() if key not in ("like", "img_name")}
        payload["title"] = "  Тестовый альбом  "
        payload["quantity"] = 0
        response = client.post("/api/products", json=payload)
        assert response.status_code == 201
        product = response.json()
        assert product["title"] == "Тестовый альбом"
        assert product["quantity"] == 0
        path = f'/api/products/{product["id"]}'
        assert client.get(path).json() == product
        assert client.patch(f"{path}/favorite").json()["like"] is True
        assert client.patch(f"{path}/favorite").json()["like"] is False
        assert client.delete(path).status_code == 204
        assert client.get(path).status_code == 404
        assert client.delete(path).status_code == 404
        assert client.patch(f"{path}/favorite").status_code == 404
        for changes in ({"title": " "}, {"price": -1}, {"quantity": -1}, {"duration": "10:99"}, {"img_href": "javascript:bad"}):
            assert client.post("/api/products", json=payload | changes).status_code == 422


def test_messages_health_covers_and_cors(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok", "database": "connected"}
        response = client.post("/api/messages", json={"email": "buyer@example.com", "problem_text": "Есть ли доставка?"})
        assert response.status_code == 201
        assert response.json()["status"] == "received"
        assert client.post("/api/messages", json={"email": "   ", "problem_text": "   "}).status_code == 422
        cover = client.get(load_mock_products()[0]["img_href"])
        assert cover.status_code == 200
        assert "image/svg+xml" in cover.headers["content-type"]
        assert client.get("/media/covers/missing.svg").status_code == 404
        response = client.options("/api/products", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        })
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_seed_preserves_existing_catalog(settings):
    with TestClient(create_app(replace(settings, seed_mock_data=False))) as client:
        assert client.get("/api/products").json() == []
        assert client.post("/api/products", json=load_mock_products()[0]).status_code == 201
    with TestClient(create_app(settings)) as client:
        assert len(client.get("/api/products").json()) == 1
