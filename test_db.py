import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from qdrant_client import QdrantClient

load_dotenv()

async def test_connections():
    print("--- Checking PostgreSQL ---")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL is missing in .env")
        return

    try:
        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM raw_documents;"))
            count = result.scalar()
            print(f"✅ Postgres OK! Documents count: {count}")
        await engine.dispose()
    except Exception as e:
        print(f"❌ Postgres Error: {e}")

    print("\n--- Checking Qdrant ---")
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        print("❌ QDRANT_URL is missing in .env")
        return

    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=10)
        collections = client.get_collections()
        col_names = [c.name for c in collections.collections]
        print(f"✅ Qdrant OK! Connected to {qdrant_url}")
        print(f"   Existing collections: {col_names if col_names else 'None'}")
    except Exception as e:
        print(f"❌ Qdrant Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connections())