# Idite Lesom — база знаний и Telegram-бот

Проект собирает материалы сайта «Идите Лесом», сохраняет их в PostgreSQL, разбивает на фрагменты, индексирует в Qdrant и отвечает на вопросы через Telegram. Для поиска используется эмбеддинг-модель **BAAI/bge-m3**, а ответы генерируются через OpenRouter. Бот старается отвечать по найденным материалам базы знаний.

## Как устроен проект

```text
src/
  bot.py                 Telegram-бот (aiogram 3)
  scraper/parser.py      обход сайта и сохранение страниц
  cleaner/               очистка Markdown
  chunking/chunker.py    разбиение документов на фрагменты
  db/                    модели и подключение к PostgreSQL
  rag/                   эмбеддинги, поиск в Qdrant и генерация ответа
scripts/
  create_chunks.py       сборка таблицы doc_chunks
  index_qdrant.py        загрузка фрагментов в Qdrant
  query_rag.py           вопрос к RAG из командной строки
tests/                   тесты
main.py                  создание таблиц и запуск скрапера
```

Путь данных:

```text
сайт → PostgreSQL (raw_documents) → фрагменты (doc_chunks) → Qdrant → поиск → OpenRouter → ответ
```

## Требования

- Python **3.14** (версия указана в `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Qdrant с доступом по URL и API-ключу
- API-ключ OpenRouter
- Telegram-бот, созданный через [@BotFather](https://t.me/BotFather)

## Установка

```bash
uv sync
uv run playwright install chromium
```

Создайте в корне проекта файл `.env` и заполните нужные значения:

```dotenv
# PostgreSQL, например: postgresql+asyncpg://user:password@localhost:5432/forest
DATABASE_URL=

# Сайт, с которого начинается обход
START_URL=https://iditelesombase.org/

# Qdrant Cloud или свой экземпляр
QDRANT_URL=
QDRANT_API_KEY=

# OpenRouter и Telegram
OPENROUTER_API_KEY=
TELEGRAM_BOT_TOKEN=

# Необязательно: токен Hugging Face для скачивания модели, если он требуется
HF_TOKEN=
```

Не добавляйте `.env` с секретами в Git.

## Первый запуск: собрать базу знаний

Выполняйте шаги по порядку из корня репозитория.

1. Создать таблицы PostgreSQL и обойти страницы `START_URL`:

   ```bash
   uv run main.py
   ```

2. Очистить Markdown и пересобрать фрагменты в таблице `doc_chunks`:

   ```bash
   uv run scripts/migrate_clean_markdown.py
   uv run scripts/create_chunks.py
   ```

3. Загрузить векторы и тексты фрагментов в коллекцию Qdrant `notion_chunks`:

   ```bash
   uv run scripts/index_qdrant.py
   ```

   Индексатор добавляет отсутствующие векторы. Флаг `--recreate` удаляет и заново создаёт коллекцию перед индексацией:

   ```bash
   uv run scripts/index_qdrant.py --recreate
   ```

   Используйте этот флаг, только если действительно хотите пересоздать коллекцию.

После обновления исходных страниц повторите этапы 1–3, чтобы обновить базу и индекс.

## Запуск бота

```bash
uv run src/bot.py
```

Бот отвечает на `/start` приветствием и принимает текстовые вопросы. Для каждого вопроса он ищет до пяти фрагментов в Qdrant и передаёт их генератору ответа. Для генерации необходимы доступные PostgreSQL/Qdrant-настройки и `OPENROUTER_API_KEY`; для запуска polling — `TELEGRAM_BOT_TOKEN`.

## Вопрос из командной строки

Проверить RAG без Telegram можно так:

```bash
uv run scripts/query_rag.py "Как обратиться за помощью?"
```

Количество найденных фрагментов задаётся параметром `--top-k`:

```bash
uv run scripts/query_rag.py --top-k 3 "Как обратиться за помощью?"
```

## Тесты

```bash
uv run pytest
```

## Детали реализации

- Для эмбеддингов и поиска используется `BAAI/bge-m3`.
- Фрагменты ограничены примерно 1024 токенами с перекрытием до 128 токенов.
- Коллекция Qdrant называется `notion_chunks`, размер вектора — 1024.
- Синхронные вызовы поиска и генерации в Telegram-обработчике запускаются через `asyncio.to_thread`, чтобы не блокировать цикл событий.
- Генератор использует модель OpenRouter `openrouter/free` по умолчанию. Системная инструкция ограничивает ответы содержимым найденных источников.
