import asyncpg
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..database import get_pool
from ..schemas import CheckoutOptions, CheckoutInput, Order, Page, Quote, QuoteInput
from ..security import current_user
from ..services.cart import make_quote, read_cart
from ..services.catalog import page_result
from ..services.orders import change_status, checkout, get_order, order_documents

router = APIRouter(tags=['Оформление и заказы'])


@router.get('/api/checkout/options', response_model=CheckoutOptions)
async def checkout_options(request: Request):
    settings = request.app.state.settings
    return {'currency': 'RUB', 'shipping_methods': [
        {'id': 'pickup', 'title': 'Самовывоз', 'fee': 0, 'address': settings.pickup_address},
        {'id': 'courier', 'title': 'Курьер', 'fee': settings.delivery_fee, 'free_from': settings.free_delivery_from},
    ], 'payment_methods': [{'id': 'on_receipt', 'title': 'Оплата при получении'}]}


@router.post('/api/checkout/quote', response_model=Quote)
async def quote(payload: QuoteInput, request: Request, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        return make_quote(await read_cart(connection, user['id']), payload.shipping_method, request.app.state.settings)


@router.post('/api/orders', status_code=201, response_model=Order)
async def create_order(payload: CheckoutInput, request: Request, response: Response,
                       idempotency_key: str = Header(..., min_length=8, max_length=128, pattern=r'^[A-Za-z0-9_-]+$'),
                       user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        result, replay = await checkout(connection, user, payload, idempotency_key, request.app.state.settings)
    response.headers['Idempotency-Replayed'] = str(replay).lower()
    if replay:
        response.status_code = 200
    return result


@router.get('/api/orders', response_model=Page[Order])
async def list_orders(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                      user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        total = await connection.fetchval('SELECT COUNT(*) FROM store_orders WHERE user_id=$1', user['id'])
        rows = await connection.fetch('SELECT * FROM store_orders WHERE user_id=$1 ORDER BY id DESC LIMIT $2 OFFSET $3',
                                      user['id'], per_page, (page-1)*per_page)
        return page_result(await order_documents(connection, rows), total, page, per_page)


@router.get('/api/orders/{order_id}', response_model=Order)
async def order(order_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
        return await get_order(connection, order_id, user['id'])


@router.post('/api/orders/{order_id}/cancel', response_model=Order)
async def cancel_order(order_id: int, user: dict = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)):
    async with pool.acquire() as connection:
        return await change_status(connection, order_id, 'cancelled', user['id'])
