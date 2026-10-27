import asyncio
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def query(settings, statement, *args, execute=False):
    async def run():
        connection = await asyncpg.connect(settings.database_url)
        try:
            if execute:
                return await connection.execute(statement, *args)
            return await connection.fetch(statement, *args)
        finally:
            await connection.close()
    return asyncio.run(run())


@pytest.fixture
def settings(tmp_path):
    database_url = os.getenv('TEST_DATABASE_URL')
    if not database_url:
        pytest.skip('Set TEST_DATABASE_URL for PostgreSQL integration tests')
    schema = f'vinil_test_{uuid4().hex}'
    admin_settings = Settings(database_url, False, ())
    query(admin_settings, f'CREATE SCHEMA "{schema}"')
    url = urlsplit(database_url)
    params = dict(parse_qsl(url.query)) | {'search_path': schema}
    try:
        yield Settings(urlunsplit(url._replace(query=urlencode(params))), True,
                       ('http://localhost:5173',), media_root=tmp_path / 'uploads')
    finally:
        query(admin_settings, f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as result:
        yield result


def register(client, email='buyer@example.com', password='secure-password-123'):
    result = client.post('/api/auth/register', json={'email': email, 'password': password, 'name': 'Покупатель'})
    assert result.status_code == 201, result.text
    data = result.json()
    return {'headers': {'Authorization': f"Bearer {data['access_token']}"}, 'data': data}


@pytest.fixture
def buyer(client):
    return register(client)


@pytest.fixture
def admin(client, settings):
    result = register(client, 'admin@example.com')
    query(settings, "UPDATE store_users SET role='admin' WHERE id=$1", result['data']['user']['id'])
    return result
