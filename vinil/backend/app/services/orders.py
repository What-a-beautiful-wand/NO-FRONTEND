"""Atomic checkout, stock reservations, immutable order snapshots, cancellation."""
import hashlib
import json

from ..errors import APIError
from .cart import make_quote, read_cart


async def order_documents(connection, rows):
    if not rows:
        return []
    result = {row['id']: dict(row) | {'number': f"VN-{row['id']:06d}", 'items': [], 'history': []} for row in rows}
    ids = list(result)
    for item in await connection.fetch('SELECT * FROM store_order_items WHERE order_id=ANY($1::bigint[]) ORDER BY id', ids):
        result[item['order_id']]['items'].append(dict(item))
    for event in await connection.fetch('SELECT * FROM store_order_events WHERE order_id=ANY($1::bigint[]) ORDER BY id', ids):
        result[event['order_id']]['history'].append(dict(event))
    return list(result.values())


async def get_order(connection, order_id, user_id=None):
    row = await connection.fetchrow('SELECT * FROM store_orders WHERE id=$1 AND ($2::bigint IS NULL OR user_id=$2)',
                                    order_id, user_id)
    if row is None:
        raise APIError(404, 'order_not_found', 'Заказ не найден')
    return (await order_documents(connection, [row]))[0]


async def checkout(connection, user, payload, key, settings):
    request_hash = hashlib.sha256(json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    async with connection.transaction():
        # Serialize cart mutation and idempotency per account, then lock products in a fixed order.
        await connection.execute('SELECT id FROM store_users WHERE id=$1 FOR UPDATE', user['id'])
        existing = await connection.fetchrow('SELECT * FROM store_orders WHERE user_id=$1 AND idempotency_key=$2', user['id'], key)
        if existing:
            if existing['request_hash'] != request_hash:
                raise APIError(409, 'idempotency_conflict', 'Этот ключ уже использован с другим телом запроса')
            return (await order_documents(connection, [existing]))[0], True
        await connection.fetch('''SELECT p.id FROM store_products p JOIN store_cart_items c ON c.product_id=p.id
            WHERE c.user_id=$1 ORDER BY p.id FOR UPDATE OF p''', user['id'])
        cart = await read_cart(connection, user['id'])
        quote = make_quote(cart, payload.shipping_method, settings)
        if payload.expected_subtotal is not None and payload.expected_subtotal != quote['subtotal']:
            raise APIError(409, 'price_changed', 'Стоимость корзины изменилась', {'subtotal': quote['subtotal']})
        row = await connection.fetchrow('''INSERT INTO store_orders
            (user_id,payment_method,shipping_method,recipient_name,email,phone,address,comment,
             subtotal,delivery_fee,total,idempotency_key,request_hash)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING *''',
            user['id'], payload.payment_method, payload.shipping_method, payload.recipient_name,
            user['email'], payload.phone, payload.address, payload.comment,
            quote['subtotal'], quote['delivery_fee'], quote['total'], key, request_hash)
        for item in cart['items']:
            product = item['product']
            await connection.execute('''INSERT INTO store_order_items
                (order_id,product_id,title,group_name,img_href,unit_price,quantity,line_total)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8)''', row['id'], product['id'], product['title'], product['group_name'],
                product['img_href'], product['price'], item['quantity'], item['line_total'])
            await connection.execute('UPDATE store_products SET quantity=quantity-$1,updated_at=NOW() WHERE id=$2',
                                     item['quantity'], product['id'])
        await connection.execute("INSERT INTO store_order_events(order_id,status) VALUES($1,'pending')", row['id'])
        await connection.execute('DELETE FROM store_cart_items WHERE user_id=$1', user['id'])
        return (await order_documents(connection, [row]))[0], False


async def change_status(connection, order_id, target, user_id=None):
    async with connection.transaction():
        row = await connection.fetchrow('''SELECT * FROM store_orders
            WHERE id=$1 AND ($2::bigint IS NULL OR user_id=$2) FOR UPDATE''', order_id, user_id)
        if row is None:
            raise APIError(404, 'order_not_found', 'Заказ не найден')
        # Customer cancellation is idempotent but only permitted before processing.
        if target == row['status']:
            return await get_order(connection, order_id, user_id)
        allowed = {'pending': {'processing', 'cancelled'},
                   'processing': {'shipped', 'completed', 'cancelled'},
                   'shipped': {'completed'}, 'completed': set(), 'cancelled': set()}
        if target not in allowed[row['status']] or (user_id is not None and row['status'] != 'pending'):
            raise APIError(409, 'invalid_order_transition', 'Нельзя изменить статус заказа таким образом')
        if target == 'shipped' and row['shipping_method'] != 'courier':
            raise APIError(409, 'invalid_order_transition', 'Самовывоз завершается из статуса processing')
        if target == 'completed' and row['status'] == 'processing' and row['shipping_method'] == 'courier':
            raise APIError(409, 'invalid_order_transition', 'Курьерский заказ сначала должен быть отправлен')
        if target == 'cancelled':
            items = await connection.fetch('SELECT product_id,quantity FROM store_order_items WHERE order_id=$1 ORDER BY product_id', order_id)
            for item in items:
                await connection.execute('UPDATE store_products SET quantity=quantity+$1,updated_at=NOW() WHERE id=$2',
                                         item['quantity'], item['product_id'])
        await connection.execute('''UPDATE store_orders SET status=$1,updated_at=NOW(),
            payment_status=CASE WHEN $1='completed' THEN 'paid' ELSE payment_status END WHERE id=$2''', target, order_id)
        await connection.execute('INSERT INTO store_order_events(order_id,status) VALUES($1,$2)', order_id, target)
        return await get_order(connection, order_id, user_id)
