import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_raw_db_url = os.getenv("DATABASE_URL", "")

# Railway/Postgres odatda "postgresql://" yoki "postgres://" ko'rinishida beradi,
# lekin bizga asyncpg drayveri uchun "postgresql+asyncpg://" kerak.
# Shu yerda avtomatik moslashtiramiz, shunda .env yoki Railway
# o'zgaruvchisiga qo'l bilan drayver nomini qo'shish shart emas.
if _raw_db_url.startswith("postgres://"):
    DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _raw_db_url.startswith("postgresql://"):
    DATABASE_URL = _raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _raw_db_url

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL .env faylida ko'rsatilmagan")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY .env faylida ko'rsatilmagan")
