"""Explicit local administrative commands; never create a default admin account."""
import argparse
import asyncio
from getpass import getpass

import asyncpg
from pydantic import ValidationError

from .config import Settings
from .database import migrate
from .schemas import RegisterInput
from .security import hash_password


async def create_admin(payload):
    connection = await asyncpg.connect(Settings.from_env().database_url)
    try:
        await migrate(connection)
        async with connection.transaction():
            # For an existing customer, preserve their password and require a separate explicit promotion.
            if await connection.fetchval('SELECT EXISTS(SELECT 1 FROM store_users WHERE email=$1)', str(payload.email).lower()):
                raise ValueError('Пользователь уже существует. Используйте promote-admin, чтобы сохранить его пароль.')
            await connection.execute('''INSERT INTO store_users(email,name,phone,password_hash,role)
                VALUES($1,$2,$3,$4,'admin')''', str(payload.email).lower(), payload.name, payload.phone, hash_password(payload.password))
    finally:
        await connection.close()


async def promote_admin(email):
    connection = await asyncpg.connect(Settings.from_env().database_url)
    try:
        result = await connection.execute("UPDATE store_users SET role='admin' WHERE email=$1", email.lower())
        if result == 'UPDATE 0':
            raise ValueError('Пользователь не найден')
    finally:
        await connection.close()


def main():
    parser = argparse.ArgumentParser(description='Управление администратором Vinil')
    parser.add_argument('command', choices=['create-admin', 'promote-admin'])
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', default='Администратор')
    args = parser.parse_args()
    try:
        if args.command == 'create-admin':
            password = getpass('Пароль (8–128 символов): ')
            if password != getpass('Повторите пароль: '):
                raise ValueError('Пароли не совпадают')
            payload = RegisterInput(email=args.email, name=args.name, password=password)
            asyncio.run(create_admin(payload))
        else:
            asyncio.run(promote_admin(args.email))
    except (ValueError, ValidationError) as exc:
        parser.exit(1, f'{exc}\n')
    print('Готово')


if __name__ == '__main__':
    main()
