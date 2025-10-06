from sqlalchemy.dialects.mysql import CHAR
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models.BaseModel import BaseModelMixin
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables from .env file
load_dotenv()

# GET THE CONFIG VALUES FROM ENVIRONMENT VARIABLES
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
APP_ENV = os.getenv("APP_ENV")

def get_database_url():
    # URL encode the password to handle special characters like @
    encoded_password = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
    return f'mysql+aiomysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
# Database URL - Consider moving this to environment variables
URL_DATABASE = get_database_url()
# Create async engine with proper configuration
engine = create_async_engine(
    URL_DATABASE,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=True,  # Set to False in production
)

# Create async session maker with explicit configuration
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Create base model


# Improved database dependency
async def get_database() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

# Initialization function
async def init_models():
    async with engine.begin() as conn:
        # Uncomment if you need to create tables
        # await conn.run_sync(Base.metadata.create_all)
        pass

# Cleanup function
async def close_models():
    await engine.dispose()