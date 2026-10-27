# Vinil Backend — руководство для фронтенда

FastAPI + PostgreSQL. Реализованы регистрация, сессии, профиль, каталог, поиск, фильтры, личное избранное, личная корзина, расчёт доставки, оформление и отмена заказов, управление товарами и заказами, загрузка обложек и обращения покупателей. React-код не изменяется: интерфейс подключается к HTTP API.

Поддерживается оплата при получении. Онлайн-эквайринг, отправка писем/SMS, восстановление пароля по почте и интеграция с транспортными службами не подключены. Заказы и обращения сохраняются в БД; администратор обрабатывает их через API. Учётных записей и паролей по умолчанию нет.

## 1. Запуск

Из `vinil/`:

```bash
# Только при первой настройке: не перезаписывайте существующий .env.
cp .env.example .env
docker compose up -d --build db backend
```

Если пользователь не имеет доступа к Docker, выполняйте команды `docker compose` через `sudo`. Docker должен быть запущен. Для запуска также существующего фронтенда: `docker compose up -d --build`.

| Адрес | Назначение |
| --- | --- |
| `http://localhost:8000/api` | Базовый адрес API |
| `http://localhost:8000/docs` | Swagger: формы запросов, модели и Authorize |
| `http://localhost:8000/redoc` | Документация OpenAPI |
| `http://localhost:8000/openapi.json` | Машиночитаемая спецификация, источник для генерации TS-клиента |
| `http://localhost:8000/health` | Проверка API и PostgreSQL |
| `http://localhost:8080/api` | API через Nginx при запуске frontend-контейнера |

Порты привязаны к `127.0.0.1`. PostgreSQL не публикуется на хост по умолчанию. Имена `backend` и `db` работают только внутри Docker, браузер должен обращаться к `localhost`.

### Администратор

Создать отдельного администратора (пароль вводится интерактивно, 8–128 символов):

```bash
docker compose exec backend python -m app.cli create-admin --email admin@example.com --name 'Администратор'
```

Либо зарегистрироваться через API и повысить существующий аккаунт без замены пароля:

```bash
docker compose exec backend python -m app.cli promote-admin --email buyer@example.com
```

После этого войдите через обычный `POST /api/auth/login`. Роль берётся из БД при каждом запросе, поэтому существующая сессия также увидит изменение.

### Разработка API без Docker

Нужны Python 3.12 и PostgreSQL. Из `vinil/` загрузите своё окружение:

```bash
set -a
. ./.env
set +a
cd backend
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Для доступа с хоста к PostgreSQL из Compose можно создать игнорируемый Git файл `vinil/compose.override.yaml`:

```yaml
services:
  db:
    ports:
      - "127.0.0.1:5432:5432"
```

Запустите `docker compose up -d db`. Для локального API подходит `DATABASE_URL` из `.env.example`. Не запускайте одновременно два API на порту 8000. Приложение само не читает `.env`: для обычного Python-процесса его нужно загрузить в окружение, как показано выше.

## 2. Общие соглашения

- Все пути ниже начинаются с `/api`, кроме `/health`, документации и файлов обложек.
- Запросы и ответы — JSON UTF-8. Для JSON-тела нужен `Content-Type: application/json`.
- Загрузка изображения — `multipart/form-data`; браузер сам выставляет Content-Type с boundary.
- Цены, суммы и доставка — **целые рубли**, валюта `RUB`. Например `4290` = 4 290 ₽. Дробные цены не отправлять.
- `id`, `product_id`, `order_id`, `user_id` — числа. Даты — ISO 8601 с часовым поясом UTC.
- Неизвестные поля входного JSON запрещены (`422`). Поля только для чтения из ответа нельзя отправлять при создании/изменении товара.
- `204` означает успех без тела: не вызывайте `response.json()` для этого ответа.
- Все персональные методы требуют `Authorization: Bearer <access_token>`.
- Каталог публичный. Если передать токен, поле `like` будет отражать избранное текущего пользователя; без токена оно `false`. Недействительный переданный токен даёт `401` даже на публичном каталоге.
- Списки товаров, избранного, заказов и обращений используют одинаковую пагинацию. `page` от 1, `per_page` от 1 до 100, по умолчанию 20. Пустой список: `total=0`, `pages=0`; страница за пределами списка содержит `items=[]`.

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "per_page": 20,
  "pages": 0
}
```

### Ошибки

```json
{
  "error": {
    "code": "stock_conflict",
    "message": "Некоторые товары недоступны в нужном количестве",
    "details": [{"product_id": 1, "requested": 2, "available": 1}]
  }
}
```

| HTTP | `error.code` | Что делать интерфейсу |
| --- | --- | --- |
| 400 | `empty_cart` | Показать пустую корзину |
| 401 | `unauthorized` | Удалить просроченный токен, предложить вход |
| 401 | `invalid_credentials` | Показать ошибку почты/пароля; при смене пароля — текущего пароля |
| 403 | `forbidden` | Скрыть административное действие |
| 404 | `product_not_found`, `order_not_found`, `message_not_found`, `not_found` | Страница/объект не существует или недоступен текущему пользователю |
| 409 | `email_exists` | Предложить вход с этой почтой |
| 409 | `stock_conflict` | Обновить корзину/остатки и показать недоступные позиции |
| 409 | `price_changed` | Пересчитать итог, получить подтверждение новой цены |
| 409 | `idempotency_conflict` | Использовать прежнее тело для повтора либо новый ключ для нового заказа |
| 409 | `invalid_order_transition` | Обновить заказ, действие больше недоступно |
| 409 | `cart_limit` | Не более 100 разных товаров |
| 413 | `file_too_large` | Обложка больше 5 МиБ |
| 422 | `validation_error`, `invalid_range`, `invalid_image` | Исправить поля/файл |
| 429 | `too_many_attempts` | Повторить вход позже; заголовок `Retry-After: 900` |
| 503 | `database_unavailable` | API запущен, БД недоступна |
| 500 | `internal_error` | Показать ошибку сервера; заказ повторять только с прежним ключом |

У `validation_error` поле `details` — массив `{field, message, type}`. Например `field="body.email"`, `field="query.per_page"`, `field="header.idempotency-key"`. У других ошибок `details` может быть `null`, объектом или массивом. Для логики используйте `code`, а не русский текст. Ошибки, сформированные внешним reverse proxy, могут иметь иной формат.

## 3. Все методы

`—` = публичный; `user` = любой вошедший пользователь; `admin` = роль администратора.

| Метод | Путь | Доступ | Ответ / назначение |
| --- | --- | --- | --- |
| GET | `/health` | — | 200, состояние API/БД |
| POST | `/api/auth/register` | — | 201, сессия и пользователь |
| POST | `/api/auth/login` | — | 200, сессия и пользователь |
| GET | `/api/auth/me` | user | 200, профиль |
| PATCH | `/api/auth/me` | user | 200, обновлённый профиль |
| PUT | `/api/auth/password` | user | 204, сменить пароль и отозвать все сессии |
| POST | `/api/auth/logout` | user | 204, отозвать текущую сессию |
| POST | `/api/auth/logout-all` | user | 204, отозвать все сессии |
| GET | `/api/products` | — | 200, `Page<Product>` |
| GET | `/api/products/filters` | — | 200, доступные значения фильтров |
| GET | `/api/products/{product_id}` | — | 200, `Product` |
| POST | `/api/products` | admin | 201, создать `Product` |
| PUT | `/api/products/{product_id}` | admin | 200, заменить поля товара |
| DELETE | `/api/products/{product_id}` | admin | 204, скрыть товар |
| PATCH | `/api/products/{product_id}/favorite` | user | 200, переключить избранное; устаревший метод |
| GET | `/api/favorites` | user | 200, `Page<Product>` |
| PUT | `/api/favorites/{product_id}` | user | 200, добавить в избранное, `Product` |
| DELETE | `/api/favorites/{product_id}` | user | 204, убрать из избранного |
| GET | `/api/cart` | user | 200, `Cart` |
| PUT | `/api/cart/items/{product_id}` | user | 200, установить количество, `Cart` |
| DELETE | `/api/cart/items/{product_id}` | user | 204, убрать позицию |
| DELETE | `/api/cart` | user | 204, очистить корзину |
| GET | `/api/checkout/options` | — | 200, доставка и способы оплаты |
| POST | `/api/checkout/quote` | user | 200, расчёт заказа |
| POST | `/api/orders` | user | 201 новый / 200 повторный, `Order` |
| GET | `/api/orders` | user | 200, `Page<Order>` текущего пользователя |
| GET | `/api/orders/{order_id}` | user | 200, свой `Order` |
| POST | `/api/orders/{order_id}/cancel` | user | 200, отменённый `Order` |
| POST | `/api/messages` | — | 201, подтверждение обращения |
| GET | `/api/admin/orders` | admin | 200, `Page<Order>` всех покупателей |
| GET | `/api/admin/orders/{order_id}` | admin | 200, любой `Order` |
| PATCH | `/api/admin/orders/{order_id}/status` | admin | 200, изменить статус, `Order` |
| GET | `/api/admin/messages` | admin | 200, `Page<Message>` |
| PATCH | `/api/admin/messages/{message_id}` | admin | 200, изменить статус, `Message` |
| POST | `/api/admin/media` | admin | 201, загрузить обложку |

Дополнительно `GET /docs`, `GET /redoc`, `GET /openapi.json`; файлы доступны по `GET /media/uploads/{filename}` и `GET /mocks/media/{filename}`. Старые локальные ресурсы `/media/...` тоже обслуживаются, если файл существует.

## 4. Аккаунт и авторизация

### Регистрация и вход

`POST /api/auth/register`:

```json
{"email":"buyer@example.com","password":"my-password-123","name":"Александр","phone":"+79990000000"}
```

Обязательны email, password и name. Имя: 2–100 символов, пробелы по краям убираются. Пароль: 8–128 символов, пробелы **значимы** и сохраняются. Телефон необязателен (`""`); если заполнен — 7–15 цифр, разрешены `+`, пробелы, `(`, `)`, `-`, общая длина до 40 символов. Почта проверяется и приводится к нижнему регистру. Роль назначается сервером: `customer`.

`POST /api/auth/login`:

```json
{"email":"buyer@example.com","password":"my-password-123"}
```

Оба метода возвращают:

```json
{
  "access_token":"непрозрачная-случайная-строка",
  "token_type":"bearer",
  "expires_at":"2026-11-03T12:00:00Z",
  "user":{"id":1,"email":"buyer@example.com","name":"Александр","phone":"+79990000000","role":"customer","created_at":"2026-10-27T12:00:00Z"}
}
```

Токен — не JWT, его не нужно декодировать. Срок по умолчанию 168 часов. Refresh-токена нет: после истечения срока требуется вход. Сервер хранит хеш токена, а пароль — salted scrypt. Cookie не используются; `credentials: 'include'` не нужен. Не помещайте токен в URL. Для Swagger нажмите Authorize и вставьте только токен.

Вход ограничен: после 10 неудачных попыток для одной почты новые попытки блокируются до конца 15-минутного окна. Успешный вход сбрасывает счётчик. Этот лимит хранится в PostgreSQL и общий для экземпляров API.

### Профиль и выход

- `GET /api/auth/me` → объект `user` из примера выше.
- `PATCH /api/auth/me` принимает **оба** поля `{"name":"Новое имя","phone":"+79990000000"}`. Phone необязателен и при пропуске станет пустой строкой. Почта и роль через этот метод не меняются.
- `PUT /api/auth/password` принимает `{"current_password":"старый пароль","new_password":"новый пароль"}`. После `204` все сессии, включая текущую, отозваны: очистите токен и покажите вход.
- `POST /api/auth/logout` без тела отзывает только текущий токен.
- `POST /api/auth/logout-all` без тела отзывает все токены пользователя.

У покупателя нет доступа к чужим корзинам, избранному и заказам. Чужой заказ возвращает `404`.

## 5. Каталог

### Модель товара `Product`

```json
{
  "id":1,"title":"Meteora","group_name":"Linkin Park","price":4290,
  "img_name":"Обложка альбома Meteora","img_href":"/mocks/media/meteora-lp.jpg",
  "year":2003,"duration":"36:43","quantity":13,"like":false,
  "genre":"Rock","description":"","label":"","format":"LP","rpm":33,
  "condition":"new","is_active":true,
  "created_at":"2026-10-27T12:00:00Z","updated_at":"2026-10-27T12:00:00Z"
}
```

| Поле | Значение / ограничение при записи |
| --- | --- |
| `title`, `group_name` | Название и исполнитель, 1–200 символов после обрезки пробелов |
| `price` | Целое число 1–10 000 000 ₽ |
| `img_href` | До 2000 символов; URL http(s), `/media/...` или `/mocks/media/...` |
| `year` | Год 1–2100 |
| `duration` | `ММ:СС`; минуты могут быть длиннее двух цифр, секунды 00–59 |
| `quantity` | Остаток, целое число 0–1 000 000 при записи; 0 = нет в наличии |
| `genre` | 1–200 символов, по умолчанию `Rock` |
| `description` | Описание до 10 000 символов, по умолчанию `""` |
| `label` | Лейбл до 200 символов, по умолчанию `""` |
| `format` | `LP`, `2LP`, `EP`, `Single`; по умолчанию `LP` |
| `rpm` | 33 или 45; по умолчанию 33 |
| `condition` | `new` или `used`; по умолчанию `new` |
| `is_active` | Видимость в магазине; по умолчанию true |
| `id`, `img_name`, `like`, `created_at`, `updated_at` | Только чтение. `img_name` формируется сервером; `like` персональный |

Относительный `img_href` нужно разрешать относительно **origin API**, а не Vite. Например `new URL(product.img_href, 'http://localhost:8000').href`. При работе через Nginx origin может совпадать с origin сайта. Не вставляйте описание/название как HTML: это обычный текст.

### Поиск и фильтры

`GET /api/products` возвращает пагинированный список.

| Query-параметр | Назначение |
| --- | --- |
| `q` | Подстрока названия или исполнителя, без учёта регистра; до 200 символов. `%` и `_` ищутся как обычные символы |
| `genre` | Точное значение жанра, без учёта регистра |
| `artist` | Точное значение `group_name`, без учёта регистра |
| `format` | LP / 2LP / EP / Single |
| `condition` | new / used |
| `year_min`, `year_max` | Включительные границы года, 1–2100 |
| `price_min`, `price_max` | Включительные границы цены, от 0 |
| `in_stock` | `true` — только остаток больше 0; по умолчанию false |
| `sort` | `newest` (по ID убыванию), `price_asc`, `price_desc`, `title`, `year_desc` |
| `page`, `per_page` | Пагинация |
| `include_inactive` | `true` — также скрытые товары; только администратору, иначе 403 |

Все условия объединяются через AND. Например:

```text
/api/products?q=Linkin&in_stock=true&price_max=5000&sort=price_asc&page=1&per_page=12
```

`GET /api/products/filters` возвращает значения по **всему активному каталогу**, без учёта текущих query-фильтров:

```json
{"genres":["Rock"],"artists":["Linkin Park","Muse"],"formats":["LP"],"price_min":3490,"price_max":10990,"year_min":2000,"year_max":2025}
```

Список исполнителей в примере сокращён. На пустом каталоге массивы пустые, границы `null`.

`GET /api/products/{product_id}` → один товар; скрытый доступен только администратору.

### Управление товарами (admin)

`POST /api/products` создаёт, `PUT /api/products/{product_id}` заменяет редактируемые поля. Обязательны title, group_name, price, img_href, year, duration и quantity; дополнительные можно не передавать, тогда будут применены значения по умолчанию. Для редактирования возьмите редактируемые поля текущего товара и измените нужные: PUT — полная форма, а не частичный PATCH.

```json
{
  "title":"Новый альбом","group_name":"Исполнитель","price":3990,
  "img_href":"/media/uploads/имя-файла.png","year":2024,"duration":"42:15","quantity":10,
  "genre":"Indie Rock","description":"Переиздание на виниле","label":"Demo Label",
  "format":"LP","rpm":33,"condition":"new","is_active":true
}
```

`DELETE /api/products/{product_id}` скрывает товар (`is_active=false`), а не удаляет его из истории заказов. Повтор для того же существующего ID тоже даёт 204. Вернуть товар можно PUT-запросом с `is_active=true`. Скрытые позиции исчезают из публичного каталога/избранного, но остаются в корзинах с `available=false` и блокируют оформление.

### Загрузка обложки (admin)

`POST /api/admin/media`, multipart-поле **file**. Допускаются настоящие JPEG, PNG и WebP до 5 МиБ и до 16 мегапикселей. Сервер проверяет содержимое, преобразует в PNG, убирает метаданные и назначает случайное имя. SVG для загрузки не принимается.

```bash
curl -X POST http://localhost:8000/api/admin/media \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F 'file=@cover.jpg'
```

Ответ 201:

```json
{"img_href":"/media/uploads/0123456789abcdef0123456789abcdef.png","width":600,"height":600}
```

Затем используйте `img_href` при создании/изменении товара. В Docker файлы сохраняются в отдельном томе `media_data`. API удаления файлов нет: старые файлы могут использоваться в снимках заказов.

## 6. Избранное

- `GET /api/favorites?page=1&per_page=20` → `Page<Product>`; только активные товары текущего пользователя.
- `PUT /api/favorites/{product_id}` без тела → `Product`, `like=true`. Повтор не создаёт дубликат.
- `DELETE /api/favorites/{product_id}` без тела → 204, в том числе если записи уже нет.
- Совместимый `PATCH /api/products/{product_id}/favorite` переключает значение и возвращает Product. Для нового фронтенда используйте PUT/DELETE: они безопасны при повторе запроса.

Вложенное поле `like` в каталоге/корзине относится к текущему аккаунту. Старое общее избранное из мок-данных не переносится пользователям.

## 7. Корзина

`GET /api/cart` → `Cart`:

```json
{
  "items":[{
    "product":{"id":1,"title":"Meteora","price":4290,"quantity":13},
    "quantity":2,"line_total":8580,"available":true
  }],
  "items_count":2,"subtotal":8580,"currency":"RUB"
}
```

`product` в примере сокращён; в реальном ответе это полный Product.

**Два разных количества:** `item.quantity` — сколько покупатель выбрал; `item.product.quantity` — складской остаток. `items_count` — сумма выбранных единиц, а не число строк.

`PUT /api/cart/items/{product_id}`:

```json
{"quantity":2}
```

Это **установка**, а не прибавление. Для кнопки «+» отправляйте текущее количество + 1. Разрешены 1–99 единиц каждой позиции и до 100 разных товаров. Сервер проверяет видимость и текущий остаток. Для удаления используйте DELETE, а не quantity=0.

`DELETE /api/cart/items/{product_id}` и `DELETE /api/cart` возвращают 204, в том числе при повторе. После удаления перечитайте корзину.

Корзина сохраняется в БД между входами. Анонимной серверной корзины нет: до регистрации храните выбор локально, затем перенесите позиции через PUT. Товары в корзине **не резервируются**. Цены и наличие пересчитываются при чтении; `available=false` означает, что товар скрыт или остаток меньше выбранного количества. Подытог включает все позиции, даже недоступные, но оформить такую корзину нельзя.

## 8. Оформление заказа

Рекомендуемая последовательность интерфейса:

1. Прочитать корзину, дать исправить недоступные позиции.
2. Прочитать `GET /api/checkout/options` и показать способы доставки/оплаты.
3. При выборе доставки вызвать `POST /api/checkout/quote`.
4. Собрать имя получателя, телефон и адрес при курьерской доставке.
5. Создать ключ `crypto.randomUUID()` и сохранить его вместе с телом запроса до получения определённого результата.
6. Отправить `POST /api/orders`. При сетевом сбое повторить с **тем же ключом и телом**.
7. После успеха показать номер заказа и перечитать корзину (сервер её очистил).

### Доставка

`GET /api/checkout/options`:

```json
{
  "currency":"RUB",
  "shipping_methods":[
    {"id":"pickup","title":"Самовывоз","fee":0,"address":"Адрес самовывоза уточнит менеджер","free_from":null},
    {"id":"courier","title":"Курьер","fee":390,"address":null,"free_from":10000}
  ],
  "payment_methods":[{"id":"on_receipt","title":"Оплата при получении"}]
}
```

Самовывоз бесплатный. Курьер по умолчанию 390 ₽, бесплатно от 10 000 ₽ включительно. Сумма порога считается по товарам без доставки. Значения настраиваются сервером; не фиксируйте их во фронтенде. Сроки/зона доставки не рассчитываются транспортной службой: укажите реальные условия магазина перед запуском.

`POST /api/checkout/quote`:

```json
{"shipping_method":"courier"}
```

Ответ:

```json
{"cart":{"items":[],"items_count":2,"subtotal":8580,"currency":"RUB"},"shipping_method":"courier","subtotal":8580,"delivery_fee":390,"total":8970,"currency":"RUB"}
```

Массив `cart.items` в этом примере сокращён; реально содержит выбранные товары. Пустая корзина даёт 400; недоступные позиции — 409. Расчёт не резервирует наличие и не фиксирует цену.

### Создать заказ

`POST /api/orders`, обязательно заголовок `Idempotency-Key` — 8–128 символов, латинские буквы, цифры, дефис/подчёркивание. Рекомендуется UUID.

```json
{
  "shipping_method":"courier",
  "payment_method":"on_receipt",
  "recipient_name":"Александр Иванов",
  "phone":"+79990000000",
  "address":"Москва, ул. Примерная, дом 10, кв. 5",
  "comment":"Позвонить перед доставкой",
  "expected_subtotal":8580
}
```

Обязательны shipping_method, recipient_name (2–100 символов), phone (правила как у профиля). payment_method по умолчанию on_receipt. address до 1000 символов; для courier минимум 10 символов, для pickup сервер сохраняет пустую строку. comment до 2000 символов, необязателен. Почта получателя берётся из аккаунта.

`expected_subtotal` необязателен, но рекомендуется: передайте subtotal из последнего quote. Если цены изменились, сервер ответит `409 price_changed`, `details={"subtotal":новая_сумма}`. После подтверждения новой суммы обновите тело и создайте **новый ключ**. Клиент не передаёт итог, стоимость доставки, товары или цены — сервер получает их из корзины и БД.

При успехе создаётся Order, складские остатки уменьшаются и корзина очищается **одной транзакцией**. При ошибке ничего из этого не применяется. Одновременные покупки не позволяют продать больше текущего остатка.

Первый успех: **201**, `Idempotency-Replayed: false`. Повтор того же ключа/тела для того же пользователя: **200**, `Idempotency-Replayed: true`, тот же заказ в его текущем статусе, даже если корзина уже пуста. Изменённые данные оформления с тем же ключом: 409. Порядок JSON-полей и явная передача значений по умолчанию не меняют смысл запроса. Ключ связан с телом оформления, а не с новой корзиной: для следующей покупки всегда создавайте новый ключ. Ключ не удаляется после отмены заказа.

### Модель заказа `Order`

```json
{
  "id":1,"number":"VN-000001","user_id":1,
  "status":"pending","payment_method":"on_receipt","payment_status":"unpaid",
  "shipping_method":"courier","recipient_name":"Александр Иванов",
  "email":"buyer@example.com","phone":"+79990000000",
  "address":"Москва, ул. Примерная, дом 10, кв. 5","comment":"",
  "subtotal":8580,"delivery_fee":390,"total":8970,"currency":"RUB",
  "items":[{"product_id":1,"title":"Meteora","group_name":"Linkin Park","img_href":"/mocks/media/meteora-lp.jpg","unit_price":4290,"quantity":2,"line_total":8580}],
  "history":[{"status":"pending","created_at":"2026-10-27T12:00:00Z"}],
  "created_at":"2026-10-27T12:00:00Z","updated_at":"2026-10-27T12:00:00Z"
}
```

Название, исполнитель, ссылка обложки, цена и количество в items — снимок на момент покупки. Изменение/скрытие товара не переписывает старый заказ. Сумма `total = subtotal + delivery_fee`. `number` нужен для показа, запросы используют числовой `id`.

### Просмотр и отмена

- `GET /api/orders?page=1&per_page=20` → Page<Order>, новые первыми.
- `GET /api/orders/{order_id}` → свой Order.
- `POST /api/orders/{order_id}/cancel` без тела → отменённый Order. Покупатель может отменить только pending. Повтор отмены уже cancelled тоже успешен, остатки возвращаются ровно один раз. Товары в корзину автоматически не возвращаются.

## 9. Административные заказы

`GET /api/admin/orders` поддерживает page, per_page и необязательный `status`. Возвращает заказы всех покупателей с контактами. `GET /api/admin/orders/{order_id}` — отдельный заказ.

`PATCH /api/admin/orders/{order_id}/status`:

```json
{"status":"processing"}
```

| Статус | Значение | Допустимый следующий статус |
| --- | --- | --- |
| `pending` | Новый заказ | processing, cancelled |
| `processing` | Принят в обработку | shipped (курьер), completed (самовывоз), cancelled |
| `shipped` | Передан в доставку | completed |
| `completed` | Выдан покупателю, оплата получена | Конечный |
| `cancelled` | Отменён, остатки возвращены | Конечный |

Повтор установки того же статуса успешен и не добавляет повторное событие. Для самовывоза shipped запрещён, для курьера нельзя перейти из processing сразу в completed. Администратор может отменить pending/processing, покупатель — только pending. После отправки автоматической отмены/возврата через API нет.

Переход в completed означает подтверждение администратором **фактической выдачи и оплаты при получении**: `payment_status` становится paid. Это не списание денег с банковской карты. Администратор должен подтверждать completed только после получения оплаты.

## 10. Обращения

`POST /api/messages`, авторизация не нужна:

```json
{"email":"buyer@example.com","tel":"+79990000000","problem_text":"Когда появится пластинка?"}
```

email — корректная почта; tel необязателен (до 40 символов); problem_text — 1–10 000 символов после обрезки пробелов.

Ответ 201:

```json
{"id":1,"status":"received","created_at":"2026-10-27T12:00:00Z"}
```

Сообщение сохранено в БД, письмо не отправляется. Для admin:

- `GET /api/admin/messages?page=1&per_page=20&status=open` → Page<Message>. status необязателен: open или resolved. Новые первыми.
- `PATCH /api/admin/messages/{message_id}` с `{"status":"resolved"}` или `{"status":"open"}` → Message.

```json
{"id":1,"email":"buyer@example.com","tel":"+79990000000","problem_text":"Когда появится пластинка?","status":"open","created_at":"2026-10-27T12:00:00Z"}
```

## 11. Пример подключения из TypeScript

Этот пример можно перенести в будущий фронтенд. Здесь BASE содержит `/api`, поэтому пути передаются без `/api`.

```ts
const API_ORIGIN = 'http://localhost:8000';
const BASE = `${API_ORIGIN}/api`;

type ApiOptions = RequestInit & { json?: unknown; token?: string };

async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { json, token, ...init } = options;
  const headers = new Headers(init.headers);
  if (json !== undefined) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${BASE}${path}`, {
    ...init, headers,
    body: json === undefined ? init.body : JSON.stringify(json),
  });
  const data = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (!response.ok) {
    throw Object.assign(new Error(data?.error?.message ?? `HTTP ${response.status}`), {
      status: response.status,
      code: data?.error?.code,
      details: data?.error?.details,
    });
  }
  return data as T;
}

// Типы AuthResponse, Page<Product>, Cart и Order возьмите из OpenAPI.
const auth = await api<AuthResponse>('/auth/login', {
  method: 'POST', json: { email: 'buyer@example.com', password: 'my-password-123' },
});
const token = auth.access_token;
const catalog = await api<Page<Product>>('/products?in_stock=true', { token });
const cart = await api<Cart>(`/cart/items/${catalog.items[0].id}`, {
  method: 'PUT', token, json: { quantity: 1 },
});

const key = crypto.randomUUID(); // Сохранить этот ключ и тело до завершения попытки заказа.
const body = {
  shipping_method: 'pickup', recipient_name: auth.user.name,
  phone: '+79990000000', expected_subtotal: cart.subtotal,
};
const order = await api<Order>('/orders', {
  method: 'POST', token, headers: { 'Idempotency-Key': key }, json: body,
});

const imageUrl = new URL(catalog.items[0].img_href, API_ORIGIN).href;

// Для загрузки обложки используйте токен администратора и реальный File из input.
async function uploadCover(file: File, adminToken: string) {
  const form = new FormData();
  form.append('file', file);
  return api<{ img_href: string; width: number; height: number }>('/admin/media', {
    method: 'POST', token: adminToken, body: form,
  });
}
```

Токен можно держать в памяти приложения; после перезагрузки страницы тогда потребуется новый вход. Если выбираете сохранять его в хранилище браузера, учитывайте доступ к нему любого выполняемого на странице скрипта. При 401 очистите сохранённый токен и состояние пользователя. При выходе очистите клиентские кеши корзины, избранного и заказов, чтобы не показать данные предыдущего аккаунта.

CORS по умолчанию разрешает `http://localhost:5173` и `http://127.0.0.1:5173`, включая Authorization и Idempotency-Key. Origin с другим портом/доменом нужно добавить в CORS_ORIGINS. При работе через Nginx можно использовать BASE=`/api` и текущий origin для обложек.

### Быстрая проверка curl

```bash
curl http://localhost:8000/health
curl 'http://localhost:8000/api/products?q=Linkin&per_page=12'
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"buyer@example.com","password":"my-password-123","name":"Покупатель"}'

# Скопируйте access_token из предыдущего ответа.
TOKEN='ваш-токен'
curl -X PUT http://localhost:8000/api/cart/items/1 \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"quantity":1}'
curl -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-order-0001' \
  -d '{"shipping_method":"pickup","recipient_name":"Покупатель","phone":"+79990000000"}'
```

ID 1 в примере подходит для новой демо-БД; в существующей используйте ID из каталога.

## 12. Настройки, данные и обслуживание

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| DATABASE_URL | `postgresql://vinil:vinil_local@localhost:5432/vinil` | Подключение локального API; в Compose адрес формируется с хостом db |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | vinil / vinil / vinil_local | Настройки PostgreSQL в Compose |
| BACKEND_PORT / FRONTEND_PORT | 8000 / 8080 | Порты на хосте |
| SEED_MOCK_DATA | false в Python, true в Compose | Однократное заполнение пустого каталога |
| CORS_ORIGINS | localhost:5173, 127.0.0.1:5173 с http:// | Разрешённые origins, через запятую |
| SESSION_HOURS | 168 | Срок сессии, больше 0 |
| DELIVERY_FEE | 390 | Цена курьерской доставки, от 0 |
| FREE_DELIVERY_FROM | 10000 | Порог бесплатной доставки; 0 = курьер всегда бесплатный |
| PICKUP_ADDRESS | Адрес самовывоза уточнит менеджер | Адрес для интерфейса оформления |
| MEDIA_ROOT | backend/static/uploads локально, /app/uploads в Compose | Каталог загруженных изображений |

Примерные пароли БД предназначены для локальной разработки. При использовании спецсимволов в пароле корректно URL-кодируйте пароль в DATABASE_URL/строке подключения Compose. Изменение POSTGRES_PASSWORD в .env не меняет пароль внутри уже инициализированного тома PostgreSQL. Обычный docker compose restart не перечитывает новое окружение: используйте `docker compose up -d --build backend`.

### Моки и миграции

Текущий `mocks/products.json` содержит твои 9 пластинок. Исходный JSON и изображения загрузчик не переписывает. Он автоматически добавляет отсутствующее img_name и значения полей товара по умолчанию. Для текущих несовпадений путей учитываются расширения jpg/png, регистр `.JPG` и опечатка trench-yop → trench-top. Файлы раздаются через `/mocks/media/...`. Жанр по умолчанию Rock — это техническое начальное значение, его можно уточнить через admin API.

`SEED_MOCK_DATA=true` заполняет только пустую таблицу и сохраняет метку `vinyl-catalog-v1` в store_seed_history. Повторные запуски не создают дубликаты, не перезаписывают твой каталог и не возвращают удалённые/скрытые товары. Правка JSON не меняет уже существующую БД. Если нужно загрузить новый набор в существующий магазин, используй API администратора; не удаляй рабочий том ради обновления моков.

При старте автоматически применяются версионные SQL-миграции из sql/migrations под блокировкой PostgreSQL. Существующие товары и обращения сохраняются. Выполненные миграции записываются с SHA-256; уже применённый файл нельзя изменять — добавляй следующий файл, например 003_feature.sql. Старый столбец store_products.is_favorite сохранён для совместимости схемы, но API использует отдельную таблицу store_favorites и не читает общее избранное.

**Изменения относительно раннего API:** GET /api/products теперь возвращает объект пагинации вместо массива; создание/изменение/скрытие товаров требует admin; избранное персональное и требует входа. Старый путь переключения избранного сохранён, но больше не глобальный.

### Команды

```bash
# Из vinil/
docker compose ps
docker compose logs -f backend
docker compose up -d --build backend
docker compose down

# Резервная копия БД на хост (включает аккаунты, заказы и обращения)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > vinil-backup.sql
```

Остановка через down сохраняет именованные тома. **docker compose down -v удаляет всю БД и все загруженные обложки.** Для резервного копирования файлов отдельно сохраняй том media_data. Не публикуй дампы/токены/пароли в Git.

Перед доступом реальных покупателей настрой HTTPS, реальные адрес/тарифы магазина, резервное копирование БД и файлов, ограничения запросов на reverse proxy (включая публичную регистрацию/обращения) и хранение секретов. Текущая Docker-конфигурация ориентирована на локальный запуск. Встроенный rate limit относится только ко входу, а не ко всему API.

## 13. Тесты и структура кода

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
# Для полного набора нужен доступный PostgreSQL с правом CREATE SCHEMA:
TEST_DATABASE_URL=postgresql://vinil:vinil_local@localhost:5432/vinil python -m pytest -q
```

Без TEST_DATABASE_URL выполняются только проверки без БД, интеграционные тесты будут skipped. Тесты создают отдельную случайную схему и удаляют её; рабочие таблицы магазина не используются. Проверяются права доступа, личные данные, поиск, CRUD, картинки, корзина, суммы, остатки, идемпотентность, статусы, отмена, параллельная покупка последнего экземпляра, повторный запуск и обновление старой схемы.

```text
backend/
├── app/
│   ├── api/          # auth, products, favorites, cart, orders, messages, admin, health
│   ├── services/     # Каталог, расчёт корзины, транзакции заказов
│   ├── config.py     # Окружение
│   ├── database.py   # Пул и миграции
│   ├── errors.py     # Единый JSON ошибок
│   ├── security.py   # scrypt, сессии, зависимости user/admin
│   ├── schemas.py    # Контракты Pydantic → OpenAPI
│   ├── seed.py       # Нормализация и однократная загрузка твоих моков
│   ├── cli.py        # Создание/повышение администратора
│   └── main.py       # Сборка приложения, CORS, статические файлы
├── sql/migrations/   # Добавляй новые версии, не редактируй применённые
├── mocks/            # Твой JSON и изображения
├── static/uploads/   # Локальные загрузки (в Docker отдельный том)
├── tests/
├── server.py         # Совместимый вход python server.py / uvicorn server:app
├── requirements.txt
├── requirements-dev.txt
└── Dockerfile
```
