from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import admin, auth, cart, favorites, health, messages, orders, products
from .config import BASE_DIR, Settings
from .database import lifespan
from .errors import install_handlers
from .schemas import ErrorEnvelope


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title='Винильчик — API магазина винила', version='1.0.0', lifespan=lifespan,
        description='Аккаунты, каталог, личное избранное, корзина, оформление заказов и администрирование. Цены в рублях.',
        responses={code: {'model': ErrorEnvelope} for code in (400, 401, 403, 404, 409, 413, 422, 429, 503)},
    )
    app.state.settings = settings
    install_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
                       allow_headers=['Content-Type', 'Authorization', 'Idempotency-Key'],
                       expose_headers=['Idempotency-Replayed', 'Retry-After'])
    for router in (health.router, auth.router, products.router, favorites.router, cart.router,
                   orders.router, messages.router, admin.router):
        app.include_router(router)
    app.mount('/media/uploads', StaticFiles(directory=settings.media_root, check_dir=False), name='uploads')
    app.mount('/media', StaticFiles(directory=BASE_DIR / 'static', check_dir=False), name='media')
    app.mount('/mocks/media', StaticFiles(directory=BASE_DIR / 'mocks' / 'media'), name='mock-media')
    return app


app = create_app()
