import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root directory
BASE_DIR = Path(__file__).resolve().parent

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set. Check your .env file.")

# Admin Telegram ID
_admin_id_raw = os.getenv("ADMIN_ID")
if not _admin_id_raw:
    raise ValueError("ADMIN_ID is not set. Check your .env file.")
try:
    ADMIN_ID = int(_admin_id_raw)
except ValueError:
    raise ValueError(f"ADMIN_ID must be an integer, got: {_admin_id_raw!r}")

# Timezone
from zoneinfo import ZoneInfo

TEACHER_TIMEZONE_NAME = os.getenv("TEACHER_TIMEZONE", "Asia/Tashkent")
try:
    TEACHER_TIMEZONE = ZoneInfo(TEACHER_TIMEZONE_NAME)
except Exception:
    raise ValueError(
        f"TEACHER_TIMEZONE is not a valid timezone: {TEACHER_TIMEZONE_NAME!r}. "
        "Use a zoneinfo name like 'Asia/Tashkent' or 'Europe/London'."
    )

# Database
DB_PATH = BASE_DIR / "english_bot.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"