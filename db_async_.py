from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database import DATABASE_URL   # тот же URL, что и у sync-движка

async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,        # под concurrency воркера
    max_overflow=0,
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)