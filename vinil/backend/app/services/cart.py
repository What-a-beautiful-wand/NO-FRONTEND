from ..errors import APIError
from .catalog import PRODUCT_SELECT, product_dict


async def read_cart(connection, user_id: int) -> dict:
    rows = await connection.fetch(PRODUCT_SELECT + ''' JOIN store_cart_items c ON c.product_id=p.id
        WHERE c.user_id=$1 ORDER BY p.id''', user_id)
    quantities = {row['product_id']: row['quantity'] for row in await connection.fetch(
        'SELECT product_id,quantity FROM store_cart_items WHERE user_id=$1', user_id)}
    items = []
    for row in rows:
        quantity = quantities[row['id']]
        items.append({'product': product_dict(row), 'quantity': quantity,
                      'line_total': row['price'] * quantity,
                      'available': row['is_active'] and row['quantity'] >= quantity})
    return {'items': items, 'items_count': sum(i['quantity'] for i in items),
            'subtotal': sum(i['line_total'] for i in items), 'currency': 'RUB'}


def validate_cart(cart):
    if not cart['items']:
        raise APIError(400, 'empty_cart', 'Корзина пуста')
    conflicts = [{'product_id': item['product']['id'], 'requested': item['quantity'],
                  'available': item['product']['quantity'] if item['product']['is_active'] else 0}
                 for item in cart['items'] if not item['available']]
    if conflicts:
        raise APIError(409, 'stock_conflict', 'Некоторые товары недоступны в нужном количестве', conflicts)


def make_quote(cart, shipping_method, settings):
    validate_cart(cart)
    fee = settings.delivery_fee if shipping_method == 'courier' and cart['subtotal'] < settings.free_delivery_from else 0
    return {'cart': cart, 'shipping_method': shipping_method, 'subtotal': cart['subtotal'],
            'delivery_fee': fee, 'total': cart['subtotal'] + fee, 'currency': 'RUB'}
