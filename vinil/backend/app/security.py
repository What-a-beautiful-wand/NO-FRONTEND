"""Salted scrypt passwords and revocable, hashed opaque bearer sessions."""
import asyncio
import hashlib
import hmac
import secrets

import asyncpg
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import get_pool
from .errors import APIError

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, maxmem=64 * 1024 * 1024)
    return f'scrypt$32768$8$3${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split('$')
        if (algorithm, n, r, p) != ('scrypt', '32768', '8', '3'):
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password('dummy-password-never-used-to-login')


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def unauthorized():
    return APIError(401, 'unauthorized', 'Необходим действующий Bearer-токен',
                    headers={'WWW-Authenticate': 'Bearer'})


async def optional_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                        pool: asyncpg.Pool = Depends(get_pool)) -> dict | None:
    if credentials is None:
        if request.headers.get('Authorization'):
            raise unauthorized()
        return None
    if len(credentials.credentials) > 512:
        raise unauthorized()
    digest = token_hash(credentials.credentials)
    async with pool.acquire() as connection:
        row = await connection.fetchrow('''SELECT u.* FROM store_users u
            JOIN store_sessions s ON s.user_id = u.id
            WHERE s.token_hash = $1 AND s.expires_at > NOW()''', digest)
    if row is None:
        raise unauthorized()
    request.state.token_hash = digest
    return dict(row)


async def current_user(user: dict | None = Depends(optional_user)) -> dict:
    if user is None:
        raise unauthorized()
    return user


async def admin_user(user: dict = Depends(current_user)) -> dict:
    if user['role'] != 'admin':
        raise APIError(403, 'forbidden', 'Нужна роль администратора')
    return user


async def issue_session(connection: asyncpg.Connection, user: dict, hours: int) -> dict:
    token = secrets.token_urlsafe(32)
    expires_at = await connection.fetchval('''INSERT INTO store_sessions(token_hash, user_id, expires_at)
        VALUES($1,$2,NOW() + $3 * INTERVAL '1 hour') RETURNING expires_at''', token_hash(token), user['id'], hours)
    return {'access_token': token, 'token_type': 'bearer', 'expires_at': expires_at, 'user': user}


async def check_password(password: str, encoded: str) -> bool:
    return await asyncio.to_thread(verify_password, password, encoded)
