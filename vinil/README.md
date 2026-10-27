# Винильчик

## Структура

```text
vinil/
├── frontend/                    # Существующий React-фронтенд
├── backend/
│   ├── app/
│   │   ├── api/                 # Каталог, обратная связь, healthcheck
│   │   ├── config.py            # Переменные окружения
│   │   ├── database.py          # Пул PostgreSQL и инициализация схемы
│   │   ├── main.py              # Создание приложения, CORS, статика
│   │   ├── schemas.py           # Валидация запросов и ответов
│   │   └── seed.py              # Однократная загрузка мок-каталога
│   ├── mocks/products.json      # 12 демонстрационных пластинок
│   ├── static/covers/           # Локальные SVG-обложки для моков
│   ├── sql/schema.sql           # Таблицы товаров, обращений и истории seed
│   ├── tests/                   # Проверки API и загрузки данных
│   ├── server.py                # Совместимый вход для старой команды запуска
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── docker/
│   ├── frontend.Dockerfile      # Сборка React и раздача через Nginx
│   └── nginx.conf               # Проксирование /api, /media и /health
├── compose.yaml                # frontend + backend + db
├── .dockerignore
├── .env.example
└── .gitignore
```

## Запуск в Docker

Команды выполняются из папки `vinil`. Нужен работающий Docker с Compose.

```bash
cp .env.example .env
docker compose up -d --build
```

- Сайт: <http://localhost:8080>
- Каталог через Nginx: <http://localhost:8080/api/products>
- Swagger API: <http://localhost:8000/docs>
- Проверка API и БД: <http://localhost:8000/health>

PostgreSQL доступен внутри сети Compose. Порты сайта и API привязаны к `127.0.0.1`; их можно изменить через `FRONTEND_PORT` и `BACKEND_PORT`. Пароли из примера предназначены для локальной разработки. Если пароль содержит специальные символы URL, используйте URL-кодирование пароля в `DATABASE_URL` и настройте соответствующее значение подключения в Compose.

```bash
docker compose ps
docker compose logs -f backend
docker compose down
```

`down` сохраняет товары и обращения в именованном томе `postgres_data`. `docker compose down -v` **удаляет все данные этой установки**, включая обращения. После следующего запуска с включённым seed появится исходный мок-каталог.

## Мок-данные

`backend/mocks/products.json` содержит 12 альбомов разных исполнителей: название, исполнитель (`group_name`), цена в целых рублях, год выпуска, длительность `ММ:СС`, остаток, избранное и путь к обложке. Есть товар с нулевым остатком для сценария «Нет в наличии». Цены и остатки вымышлены; SVG — демонстрационные изображения, а не оригинальные обложки.

При `SEED_MOCK_DATA=true` API заполняет **только пустой каталог** и записывает применение набора `vinyl-catalog-v1` в `store_seed_history`. Повторный запуск не создаёт дубликаты, не возвращает удалённые товары и не меняет существующий каталог. В Compose seed включён по умолчанию; для пустой БД задайте `SEED_MOCK_DATA=false` перед первым запуском. Изменение JSON не обновляет уже загруженные записи.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/health` | Проверка подключения к БД |
| GET | `/api/products` | Все товары |
| GET | `/api/products/{id}` | Один товар |
| POST | `/api/products` | Добавить товар |
| PATCH | `/api/products/{id}/favorite` | Переключить избранное |
| DELETE | `/api/products/{id}` | Удалить товар |
| POST | `/api/messages` | Сохранить обращение покупателя |
| GET | `/media/covers/{filename}` | Локальная обложка |

Пример создания товара:

```bash
curl -X POST http://localhost:8000/api/products \
  -H 'Content-Type: application/json' \
  -d '{"title":"Тестовый альбом","group_name":"Исполнитель","price":2990,"img_href":"/media/covers/vinyl-01.svg","year":2024,"duration":"42:30","quantity":5}'
```

Пример обращения:

```bash
curl -X POST http://localhost:8000/api/messages \
  -H 'Content-Type: application/json' \
  -d '{"email":"buyer@example.com","tel":"","problem_text":"Когда появится пластинка?"}'
```

Избранное пока общее для каталога. Авторизация, личные корзины, заказы, оплата и доставка ещё не реализованы; изменяющие API-методы открыты для локальной разработки.

## Разработка без контейнера API

Используйте Python 3.12 и PostgreSQL 17 (как в контейнерах). Настройки читаются из окружения процесса; `.env` автоматически читает только Compose.

```bash
# Из vinil; установите собственный DATABASE_URL либо используйте локальные значения .env.example.
set -a
. ./.env
set +a
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Для подключения к БД Compose с хоста создайте локальный override:

```yaml
# compose.override.yaml (локальный override уже исключён из Git)
services:
  db:
    ports:
      - "127.0.0.1:5432:5432"
```

После `docker compose up -d db` БД будет доступна по `DATABASE_URL` из примера. При запуске API на хосте остановите контейнер API или используйте другой порт, чтобы избежать конфликта.

Фронтенд запускается отдельно из `frontend` командами `npm ci` и `npm run dev`. CORS разрешает `http://localhost:5173` и `http://127.0.0.1:5173`; другие адреса задаются списком `CORS_ORIGINS` через запятую. Для будущих запросов из Vite используйте адрес API `http://localhost:8000`; при запуске в Docker доступны относительные пути `/api/...` через Nginx.

## Проверки

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
# Для всех интеграционных проверок укажите доступный PostgreSQL:
TEST_DATABASE_URL=postgresql://vinil:vinil_local@localhost:5432/vinil python -m pytest -q
```

Без `TEST_DATABASE_URL` выполняется проверка мок-каталога, а интеграционные тесты пропускаются. Каждый тест создаёт отдельную временную схему и удаляет её после выполнения; существующие таблицы магазина не используются. Пользователь тестовой БД должен иметь право создавать схемы.

```bash
cd frontend
npm run build
npm run lint
```
