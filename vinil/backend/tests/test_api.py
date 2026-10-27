from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.config import BASE_DIR
from app.main import create_app
from app.schemas import ProductInput
from app.seed import load_mock_products
from app.security import hash_password, verify_password
from conftest import query, register


def product(client):
    return client.get('/api/products').json()['items'][0]


def payload(item):
    return ProductInput.model_validate({k: v for k, v in item.items() if k in ProductInput.model_fields}).model_dump()


def checkout_body(**changes):
    return {'shipping_method': 'pickup', 'recipient_name': 'Покупатель', 'phone': '+79990000000', **changes}


def add_cart(client, buyer, product_id, quantity=1):
    response = client.put(f'/api/cart/items/{product_id}', json={'quantity': quantity}, headers=buyer['headers'])
    assert response.status_code == 200, response.text
    return response.json()


def place_order(client, buyer, body=None, key=None):
    return client.post('/api/orders', json=body or checkout_body(),
                       headers=buyer['headers'] | {'Idempotency-Key': key or str(uuid4())})


def test_password_hashing():
    encoded = hash_password('password')
    assert encoded != hash_password('password')
    assert verify_password('password', encoded)
    assert not verify_password('wrong', encoded)
    assert not verify_password('password', 'invalid')


def test_mock_catalog():
    products = load_mock_products()
    assert products
    assert len({(item['title'], item['group_name']) for item in products}) == len(products)
    for item in products:
        ProductInput.model_validate({k: v for k, v in item.items() if k != 'img_name'})
        assert (BASE_DIR / item['img_href'].lstrip('/')).is_file()


def test_registration_login_profile_and_permissions(client, buyer):
    data = buyer['data']
    assert data['user']['role'] == 'customer'
    assert 'password_hash' not in data['user']
    assert client.get('/api/auth/me', headers=buyer['headers']).json()['email'] == 'buyer@example.com'
    duplicate = client.post('/api/auth/register', json={'email': 'BUYER@example.com', 'password': 'test-test', 'name': 'Имя'})
    assert duplicate.status_code == 409
    assert duplicate.json()['error']['code'] == 'email_exists'
    login = client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': 'secure-password-123'})
    assert login.status_code == 200
    assert client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': 'wrong'}).status_code == 401
    assert client.get('/api/cart').status_code == 401
    assert client.get('/api/admin/orders', headers=buyer['headers']).status_code == 403
    assert client.post('/api/products', json=payload(load_mock_products()[0]), headers=buyer['headers']).status_code == 403
    profile = client.patch('/api/auth/me', headers=buyer['headers'], json={'name': '  Новое имя  ', 'phone': '+79990000000'})
    assert profile.json()['name'] == 'Новое имя'
    assert client.patch('/api/auth/me', headers=buyer['headers'], json={'name': 'Имя', 'role': 'admin'}).status_code == 422
    assert client.post('/api/auth/logout', headers=buyer['headers']).status_code == 204
    assert client.get('/api/auth/me', headers=buyer['headers']).status_code == 401
    assert client.get('/api/auth/me', headers={'Authorization': f"Bearer {login.json()['access_token']}"}).status_code == 200


def test_password_change_logout_all_and_expiration(client, buyer, settings):
    response = client.put('/api/auth/password', headers=buyer['headers'], json={
        'current_password': 'secure-password-123', 'new_password': '  new-password  '})
    assert response.status_code == 204
    assert client.get('/api/auth/me', headers=buyer['headers']).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': 'secure-password-123'}).status_code == 401
    login = client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': '  new-password  '})
    assert login.status_code == 200
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    assert client.post('/api/auth/logout-all', headers=headers).status_code == 204
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    login = client.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': '  new-password  '})
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    assert client.get('/api/auth/me', headers=headers).status_code == 200
    query(settings, "UPDATE store_sessions SET expires_at=NOW()-INTERVAL '1 hour'")
    assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_login_throttle(client):
    for _ in range(10):
        assert client.post('/api/auth/login', json={'email': 'unknown@example.com', 'password': 'bad'}).status_code == 401
    response = client.post('/api/auth/login', json={'email': 'unknown@example.com', 'password': 'bad'})
    assert response.status_code == 429
    assert response.headers['Retry-After'] == '900'


def test_catalog_filters_pagination_and_admin_crud(client, admin):
    expected = len(load_mock_products())
    assert client.get('/api/products').json()['total'] == expected
    page = client.get('/api/products?per_page=2&sort=price_asc').json()
    assert len(page['items']) == 2
    assert page['items'][0]['price'] <= page['items'][1]['price']
    assert client.get('/api/products?page=9999').json()['items'] == []
    assert client.get('/api/products?q=Linkin').json()['total'] == 2
    assert client.get('/api/products?q=%25').json()['total'] == 0
    assert client.get('/api/products?price_min=50&price_max=10').status_code == 422
    assert client.get('/api/products?per_page=101').status_code == 422
    assert client.get('/api/products?include_inactive=true').status_code == 403
    filters = client.get('/api/products/filters').json()
    assert 'Rock' in filters['genres']
    new = payload(product(client)) | {'title': 'Тестовый альбом', 'quantity': 0, 'genre': 'Jazz'}
    response = client.post('/api/products', headers=admin['headers'], json=new)
    assert response.status_code == 201, response.text
    pid = response.json()['id']
    assert client.get('/api/products?genre=Jazz&in_stock=true').json()['total'] == 0
    new['quantity'] = 7
    assert client.put(f'/api/products/{pid}', headers=admin['headers'], json=new).json()['quantity'] == 7
    assert client.delete(f'/api/products/{pid}', headers=admin['headers']).status_code == 204
    assert client.get(f'/api/products/{pid}').status_code == 404
    assert client.get(f'/api/products/{pid}', headers=admin['headers']).json()['is_active'] is False
    assert client.get('/api/products?include_inactive=true', headers=admin['headers']).json()['total'] == expected + 1


def test_personal_favorites(client, buyer):
    other = register(client, 'other@example.com')
    pid = product(client)['id']
    for _ in range(2):
        assert client.put(f'/api/favorites/{pid}', headers=buyer['headers']).json()['like'] is True
    assert client.get('/api/favorites', headers=buyer['headers']).json()['total'] == 1
    assert client.get('/api/favorites', headers=other['headers']).json()['total'] == 0
    assert client.get(f'/api/products/{pid}', headers=other['headers']).json()['like'] is False
    assert client.get(f'/api/products/{pid}', headers=buyer['headers']).json()['like'] is True
    assert client.get(f'/api/products/{pid}').json()['like'] is False
    assert client.patch(f'/api/products/{pid}/favorite', headers=buyer['headers']).json()['like'] is False
    assert client.delete(f'/api/favorites/{pid}', headers=buyer['headers']).status_code == 204


def test_cart_quantity_limits_isolation_and_price_changes(client, buyer, admin):
    item = product(client)
    pid = item['id']
    cart = add_cart(client, buyer, pid, 2)
    assert cart['subtotal'] == 2 * item['price']
    assert cart['items_count'] == 2
    assert add_cart(client, buyer, pid, 1)['items_count'] == 1
    other = register(client, 'other@example.com')
    assert client.get('/api/cart', headers=other['headers']).json()['items'] == []
    assert client.put(f'/api/cart/items/{pid}', json={'quantity': 0}, headers=buyer['headers']).status_code == 422
    assert client.put(f'/api/cart/items/{pid}', json={'quantity': 99}, headers=buyer['headers']).status_code == 409
    new = payload(item) | {'price': 100, 'quantity': 0}
    assert client.put(f'/api/products/{pid}', headers=admin['headers'], json=new).status_code == 200
    cart = client.get('/api/cart', headers=buyer['headers']).json()
    assert cart['subtotal'] == 100
    assert cart['items'][0]['available'] is False
    assert place_order(client, buyer).status_code == 409
    assert client.delete(f'/api/cart/items/{pid}', headers=buyer['headers']).status_code == 204
    assert client.delete('/api/cart', headers=buyer['headers']).status_code == 204
    assert place_order(client, buyer).json()['error']['code'] == 'empty_cart'


def test_checkout_quotes_orders_and_idempotency(client, buyer):
    item = product(client)
    add_cart(client, buyer, item['id'], 2)
    options = client.get('/api/checkout/options').json()
    assert options['payment_methods'][0]['id'] == 'on_receipt'
    quote = client.post('/api/checkout/quote', headers=buyer['headers'], json={'shipping_method': 'courier'}).json()
    assert quote['total'] == 2 * item['price'] + (390 if 2 * item['price'] < 10000 else 0)
    assert place_order(client, buyer, checkout_body(expected_subtotal=1)).json()['error']['code'] == 'price_changed'
    body = checkout_body(expected_subtotal=2 * item['price'])
    key = str(uuid4())
    response = place_order(client, buyer, body, key)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order['items'][0]['unit_price'] == item['price']
    assert order['status'] == 'pending'
    assert 'idempotency_key' not in order and 'request_hash' not in order
    assert client.get('/api/cart', headers=buyer['headers']).json()['items'] == []
    assert client.get(f"/api/products/{item['id']}").json()['quantity'] == item['quantity'] - 2
    replay = place_order(client, buyer, body, key)
    assert replay.status_code == 200
    assert replay.headers['Idempotency-Replayed'] == 'true'
    assert replay.json()['id'] == order['id']
    assert place_order(client, buyer, body | {'comment': 'new'}, key).json()['error']['code'] == 'idempotency_conflict'
    assert client.get('/api/orders', headers=buyer['headers']).json()['total'] == 1
    assert client.get(f"/api/orders/{order['id']}", headers=buyer['headers']).status_code == 200
    other = register(client, 'other@example.com')
    assert client.get(f"/api/orders/{order['id']}", headers=other['headers']).status_code == 404
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=other['headers']).status_code == 404
    for _ in range(2):
        assert client.post(f"/api/orders/{order['id']}/cancel", headers=buyer['headers']).json()['status'] == 'cancelled'
    assert client.get(f"/api/products/{item['id']}").json()['quantity'] == item['quantity']


def test_order_snapshot_and_admin_transitions(client, buyer, admin):
    item = product(client)
    add_cart(client, buyer, item['id'])
    order = place_order(client, buyer, checkout_body(shipping_method='courier', address='Москва, ул. Тестовая, 10')).json()
    path = f"/api/admin/orders/{order['id']}/status"
    def status(value):
        return client.patch(path, json={'status': value}, headers=admin['headers'])
    assert status('shipped').status_code == 409
    assert status('processing').status_code == 200
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=buyer['headers']).status_code == 409
    assert status('completed').status_code == 409
    assert status('shipped').status_code == 200
    assert status('cancelled').status_code == 409
    completed = status('completed').json()
    assert completed['payment_status'] == 'paid'
    assert len(completed['history']) == 4
    assert status('pending').status_code == 409
    assert client.put(f"/api/products/{item['id']}", headers=admin['headers'], json=payload(item) | {'title': 'Изменено', 'price': 100}).status_code == 200
    assert client.get(f"/api/orders/{order['id']}", headers=buyer['headers']).json()['items'][0]['unit_price'] == item['price']
    assert client.delete(f"/api/products/{item['id']}", headers=admin['headers']).status_code == 204
    assert client.get(f"/api/orders/{order['id']}", headers=buyer['headers']).json()['items'][0]['title'] == item['title']
    assert client.get('/api/admin/orders?status=completed', headers=admin['headers']).json()['total'] == 1
    assert client.get(f"/api/admin/orders/{order['id']}", headers=admin['headers']).status_code == 200


def test_concurrent_last_copy_and_double_cancel(client, buyer, admin):
    second = register(client, 'other@example.com')
    item = product(client)
    assert client.put(f"/api/products/{item['id']}", headers=admin['headers'], json=payload(item) | {'quantity': 1}).status_code == 200
    for account in (buyer, second):
        add_cart(client, account, item['id'])
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda account: place_order(client, account), (buyer, second)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    winner = (buyer, second)[next(i for i, r in enumerate(responses) if r.status_code == 201)]
    order_id = next(r.json()['id'] for r in responses if r.status_code == 201)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.post(f'/api/orders/{order_id}/cancel', headers=winner['headers']), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert client.get(f"/api/products/{item['id']}").json()['quantity'] == 1


def test_media_messages_errors_and_cors(client, buyer, admin):
    for item in load_mock_products():
        assert client.get(item['img_href']).status_code == 200
    image = BytesIO()
    Image.new('RGB', (16, 16), 'red').save(image, format='JPEG')
    response = client.post('/api/admin/media', headers=admin['headers'], files={'file': ('cover.jpg', image.getvalue(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    assert client.get(response.json()['img_href']).headers['content-type'] == 'image/png'
    assert client.post('/api/admin/media', headers=admin['headers'], files={'file': ('bad.png', b'bad', 'image/png')}).status_code == 422
    assert client.post('/api/admin/media', headers=admin['headers'], files={'file': ('huge.png', b'X' * (5*1024*1024+1), 'image/png')}).status_code == 413
    message = client.post('/api/messages', json={'email': 'buyer@example.com', 'problem_text': 'Есть доставка?'})
    assert message.status_code == 201
    mid = message.json()['id']
    assert client.get('/api/admin/messages', headers=buyer['headers']).status_code == 403
    assert client.get('/api/admin/messages?status=open', headers=admin['headers']).json()['total'] == 1
    assert client.patch(f'/api/admin/messages/{mid}', headers=admin['headers'], json={'status': 'resolved'}).json()['status'] == 'resolved'
    assert client.get('/health').json()['status'] == 'ok'
    assert client.get('/missing').json()['error']['code'] == 'not_found'
    assert client.get('/media/missing.png').status_code == 404
    assert client.get('/api/products?per_page=0').json()['error']['details'][0]['field'] == 'query.per_page'
    cors = client.options('/api/orders', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
                                                'Access-Control-Request-Headers': 'Authorization,Idempotency-Key,Content-Type'})
    assert cors.status_code == 200
    assert cors.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_restart_seed_and_legacy_migration(settings):
    # Mimic the original server's schema (before versioned migrations) and existing catalog.
    query(settings, (BASE_DIR / 'sql/migrations/001_initial.sql').read_text(), execute=True)
    query(settings, 'ALTER TABLE store_products DROP CONSTRAINT store_products_quantity_check; ALTER TABLE store_products ADD CONSTRAINT store_products_quantity_check CHECK(quantity > 0)', execute=True)
    query(settings, '''INSERT INTO store_products(title,group_name,price,img_name,img_href,year,duration,quantity)
        VALUES('Мой альбом','Мой артист',100,'Обложка','/media/test.png',2020,'10:00',1)''')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/products').json()['total'] == 1
        admin = register(client, 'admin@example.com')
        query(settings, "UPDATE store_users SET role='admin'")
        current = product(client)
        pid = current['id']
        assert client.put(f'/api/products/{pid}', headers=admin['headers'], json=payload(current) | {'quantity': 0}).status_code == 200
        assert client.delete(f'/api/products/{pid}', headers=admin['headers']).status_code == 204
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/products').json()['total'] == 0
        assert len(query(settings, 'SELECT * FROM store_schema_migrations')) == 2


def test_disabled_seed_and_repeated_start(settings):
    with TestClient(create_app(replace(settings, seed_mock_data=False))) as client:
        assert client.get('/api/products').json()['total'] == 0
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/products').json()['total'] == len(load_mock_products())
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/products').json()['total'] == len(load_mock_products())


def test_concurrent_checkout_replay(client, buyer):
    item = product(client)
    add_cart(client, buyer, item['id'])
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: place_order(client, buyer, key=key), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].json()['id'] == responses[1].json()['id']
    assert client.get(f"/api/products/{item['id']}").json()['quantity'] == item['quantity'] - 1


def test_large_order_totals(client, buyer, admin):
    items = client.get('/api/products?per_page=3').json()['items']
    for item in items:
        response = client.put(f"/api/products/{item['id']}", headers=admin['headers'],
                              json=payload(item) | {'price': 10000000, 'quantity': 99})
        assert response.status_code == 200
        add_cart(client, buyer, item['id'], 99)
    order = place_order(client, buyer)
    assert order.status_code == 201, order.text
    assert order.json()['total'] == 2970000000


def test_admin_cli_functions(client, settings, monkeypatch):
    import asyncio
    import pytest
    from app.cli import create_admin, promote_admin
    from app.schemas import RegisterInput

    monkeypatch.setenv('DATABASE_URL', settings.database_url)
    data = RegisterInput(email='cli@example.com', name='Администратор', password='cli-password-123')
    asyncio.run(create_admin(data))
    with pytest.raises(ValueError):
        asyncio.run(create_admin(data))
    login = client.post('/api/auth/login', json={'email': str(data.email), 'password': data.password})
    assert login.status_code == 200
    assert login.json()['user']['role'] == 'admin'
    buyer = register(client, 'promote@example.com')
    asyncio.run(promote_admin('promote@example.com'))
    assert client.get('/api/auth/me', headers=buyer['headers']).json()['role'] == 'admin'
