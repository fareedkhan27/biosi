import asyncio

from app.db.seeds import seed_reference_data
from app.db.session import AsyncSessionLocal


async def run_seed() -> None:
    async with AsyncSessionLocal() as session:
        await seed_reference_data(session)


if __name__ == "__main__":
    asyncio.run(run_seed())
