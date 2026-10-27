import asyncio

import asyncpg
from fastapi import APIRouter, Depends, Request, Response

from ..database import get_pool
from ..errors import APIError
from ..schemas import AuthResponse, LoginInput, PasswordInput, ProfileInput, RegisterInput, User
from ..security import DUMMY_HASH, check_password, current_user, hash_password, issue_session

router = APIRouter(prefix='/api/auth', tags=['Аккаунт'])


@router.post('/register', status_code=201, response_model=AuthResponse)
async def register(payload: RegisterInput, request: Request, pool: asyncpg.Pool = Depends(get_pool)):
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    try:
        async with pool.acquire() as connection, connection.transaction():
            user = await connection.fetchrow('''INSERT INTO store_users(email,name,phone,password_hash)
                VALUES($1,$2,$3,$4) RETURNING *''', str(payload.email).lower(), payload.name, payload.phone, password_hash)
            return await issue_session(connection, dict(user), request.app.state.settings.session_hours)
    except asyncpg.UniqueViolationError:
        raise APIError(409, 'email_exists', 'Пользователь с такой почтой уже зарегистрирован')


@router.post('/login', response_model=AuthResponse)
async def login(payload: LoginInput, request: Request, pool: asyncpg.Pool = Depends(get_pool)):
    email = str(payload.email).lower()
    result = None
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute('SELECT pg_advisory_xact_lock(hashtextextended($1, 7401002))', email)
        blocked = await connection.fetchval('''SELECT failures >= 10 AND
            window_started > NOW() - INTERVAL '15 minutes' FROM store_login_attempts WHERE email=$1''', email)
        if blocked:
            raise APIError(429, 'too_many_attempts', 'Повторите вход через 15 минут', headers={'Retry-After': '900'})
        user = await connection.fetchrow('SELECT * FROM store_users WHERE email=$1 FOR UPDATE', email)
        valid = await check_password(payload.password, user['password_hash'] if user else DUMMY_HASH)
        if not valid or user is None:
            await connection.execute('''INSERT INTO store_login_attempts(email,failures) VALUES($1,1)
                ON CONFLICT(email) DO UPDATE SET
                failures=CASE WHEN store_login_attempts.window_started <= NOW() - INTERVAL '15 minutes'
                    THEN 1 ELSE store_login_attempts.failures + 1 END,
                window_started=CASE WHEN store_login_attempts.window_started <= NOW() - INTERVAL '15 minutes'
                    THEN NOW() ELSE store_login_attempts.window_started END''', email)
        else:
            await connection.execute('DELETE FROM store_login_attempts WHERE email=$1', email)
            result = await issue_session(connection, dict(user), request.app.state.settings.session_hours)
    if result is None:
        raise APIError(401, 'invalid_credentials', 'Неверная почта или пароль')
    return result


@router.get('/me', response_model=User)
async def me(user: dict = Depends(current_user)):
    return user


@router.patch('/me', response_model=User)
async def update_me(payload: ProfileInput, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        return dict(await connection.fetchrow('UPDATE store_users SET name=$1,phone=$2 WHERE id=$3 RETURNING *',
                                              payload.name, payload.phone, user['id']))


@router.post('/logout', status_code=204, response_class=Response)
async def logout(request: Request, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        await connection.execute('DELETE FROM store_sessions WHERE token_hash=$1', request.state.token_hash)
    return Response(status_code=204)


@router.post('/logout-all', status_code=204, response_class=Response)
async def logout_all(user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        await connection.execute('DELETE FROM store_sessions WHERE user_id=$1', user['id'])
    return Response(status_code=204)


@router.put('/password', status_code=204, response_class=Response)
async def change_password(payload: PasswordInput, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction():
        row = await connection.fetchrow('SELECT * FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        if not await check_password(payload.current_password, row['password_hash']):
            raise APIError(401, 'invalid_credentials', 'Неверный текущий пароль')
        encoded = await asyncio.to_thread(hash_password, payload.new_password)
        await connection.execute('UPDATE store_users SET password_hash=$1 WHERE id=$2', encoded, user['id'])
        await connection.execute('DELETE FROM store_sessions WHERE user_id=$1', user['id'])
    return Response(status_code=204)
