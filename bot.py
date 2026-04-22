import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database.db import init_db
from handlers import common, admin, student

logging.basicConfig(level=logging.INFO)


async def main():
    # Initialize the database (creates tables if they don't exist)
    await init_db()
    logging.info("Database initialized.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(admin.router)
    dp.include_router(student.router)
    dp.include_router(common.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())