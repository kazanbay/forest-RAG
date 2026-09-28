import asyncio
from src.db.session import init_db
from src.scraper.parser import run_scraper

async def main():
    print("🚀 Инициализируем таблицы в PostgreSQL...")
    await init_db()
    
    print("🕵️ Запускаем скрапер базы знаний...")
    await run_scraper()
    
    print("✅ Сбор данных завершен!")

if __name__ == "__main__":
    asyncio.run(main())