from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine,async_sessionmaker

from app.config.config import settings
from sqlalchemy.ext.declarative import declarative_base


SQLALCHEMY_DATABASE_URL = f'postgresql+asyncpg://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}'
 
engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
 
Base = declarative_base()

session = async_sessionmaker(
    autoflush = False,
    class_=AsyncSession,
    expire_on_commit=False,
    bind=engine
)
 
async def get_db():
    async with session() as db:
        try:
            yield db
        finally:
            await db.close()

