"""Configuration is read from the process environment (Compose loads .env)."""
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_url: str
    seed_mock_data: bool
    cors_origins: tuple[str, ...]
    session_hours: int = 168
    delivery_fee: int = 390
    free_delivery_from: int = 10000
    pickup_address: str = 'Адрес самовывоза уточнит менеджер'
    media_root: Path = BASE_DIR / 'static' / 'uploads'

    @classmethod
    def from_env(cls) -> 'Settings':
        result = cls(
            database_url=os.getenv('DATABASE_URL', 'postgresql://vinil:vinil_local@localhost:5432/vinil'),
            seed_mock_data=os.getenv('SEED_MOCK_DATA', 'false').lower() == 'true',
            cors_origins=tuple(value.strip() for value in os.getenv(
                'CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173'
            ).split(',') if value.strip()),
            session_hours=int(os.getenv('SESSION_HOURS', '168')),
            delivery_fee=int(os.getenv('DELIVERY_FEE', '390')),
            free_delivery_from=int(os.getenv('FREE_DELIVERY_FROM', '10000')),
            pickup_address=os.getenv('PICKUP_ADDRESS', 'Адрес самовывоза уточнит менеджер'),
            media_root=Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'static' / 'uploads'))),
        )
        if result.session_hours <= 0 or result.delivery_fee < 0 or result.free_delivery_from < 0:
            raise ValueError('Invalid session or delivery settings')
        return result
