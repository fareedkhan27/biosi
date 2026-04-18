"""FastAPI dependency injection helpers shared across all routes."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it after the request."""
    async with AsyncSessionLocal() as session:
        yield session


# Re-export as a typed dependency alias used in route signatures:
#   async def my_route(db: DbSession) -> ...:
DbSession = AsyncSession
