import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

# Provide a fallback for alembic without env loaded if needed, or rely on .env loading in env.py
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

class DynamicAsyncSessionMaker:
    def __init__(self):
        self._maker = None
        self._loop = None

    def _get_maker(self):
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        
        if self._maker is None or self._loop != current_loop:
            # Recreate engine and sessionmaker
            new_engine = create_async_engine(DATABASE_URL, echo=False)
            self._maker = async_sessionmaker(
                bind=new_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self._loop = current_loop
        return self._maker

    def __call__(self, *args, **kwargs):
        return self._get_maker()(*args, **kwargs)

AsyncSessionLocal = DynamicAsyncSessionMaker()

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
