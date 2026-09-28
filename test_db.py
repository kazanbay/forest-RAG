import asyncio
from src.db.session import init_db, engine
from src.db.models import RawDocument

async def main():
    print("Проверяем подключение к Synology PostgreSQL...")
    try:
        await init_db()
        print(" Успешно! Таблица 'raw_documents' создана (или уже существовала).")
    except Exception as e:
        print(f" Ошибка подключения: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())