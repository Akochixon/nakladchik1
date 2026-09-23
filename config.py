import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
