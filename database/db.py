from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DB_URL
from database.models import Base


# The engine is the low-level connection pool.
# echo=False means don't print every SQL query. Flip to True if you want to debug.
engine = create_async_engine(DB_URL, echo=False)

# Session factory. Each call to `async_session()` gives you a new session.
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables defined on Base if they don't exist yet.

    Called once on bot startup. Safe to call on every run — existing
    tables are left alone.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)