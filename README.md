# Idite Lesom — Knowledge Base & Telegram Assistant

[Русская версия](README.ru.md)

Idite Lesom is a retrieval-augmented generation (RAG) project that collects public knowledge base pages, indexes their content, and answers questions in Telegram. The pipeline combines a website scraper, PostgreSQL, Qdrant vector search, **BAAI/bge-m3** embeddings, and answer generation through OpenRouter.

This repository is a practical example of an end-to-end RAG application: data ingestion, content cleanup, token-aware chunking, vector indexing, retrieval, and an async Telegram interface.

## How it works

```text
Website → PostgreSQL → Cleaned chunks → Qdrant → Top-k retrieval → OpenRouter → Answer
```

The assistant retrieves up to five relevant chunks for each question and instructs the language model to ground its response in those sources.

## Project structure

```text
src/
  bot.py                 Telegram bot (aiogram 3)
  scraper/parser.py      Website crawler and PostgreSQL ingestion
  cleaner/               Markdown cleanup for RAG
  chunking/chunker.py    Header-aware, token-bounded chunking
  db/                    PostgreSQL models and sessions
  rag/                   BGE-M3 embeddings, Qdrant retrieval, answer generation
scripts/
  create_chunks.py       Build the doc_chunks table
  index_qdrant.py        Embed and upload chunks to Qdrant
  query_rag.py           Ask the RAG pipeline from the command line
tests/                   Automated tests
main.py                  Initialize database tables and run the scraper
```

## Technology

- Python **3.14** and [uv](https://docs.astral.sh/uv/)
- [aiogram 3](https://docs.aiogram.dev/en/latest/) for the Telegram bot
- PostgreSQL and SQLAlchemy for storing scraped documents and chunks
- [Qdrant](https://qdrant.tech/) for vector search
- **BAAI/bge-m3** for 1024-dimensional embeddings (CPU)
- [OpenRouter](https://openrouter.ai/) for grounded answer generation (`openrouter/free` by default)
- Playwright for crawling web pages

## Requirements

- Python 3.14
- PostgreSQL database
- Qdrant instance and API key
- OpenRouter API key
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

Install dependencies and the Chromium browser used by Playwright:

```bash
uv sync
uv run playwright install chromium
```

Create a `.env` file in the repository root:

```dotenv
# PostgreSQL, for example: postgresql+asyncpg://user:password@localhost:5432/forest
DATABASE_URL=

# Website entry point for the crawler
START_URL=https://iditelesombase.org/

# Qdrant Cloud or self-hosted instance
QDRANT_URL=
QDRANT_API_KEY=

# External API credentials
OPENROUTER_API_KEY=
TELEGRAM_BOT_TOKEN=

# Optional: Hugging Face token, if required to download the model
HF_TOKEN=
```

Keep credentials private; do not commit your `.env` file.

## Build the knowledge base

Run these steps from the repository root, in order.

1. Create the PostgreSQL tables and crawl pages starting at `START_URL`:

   ```bash
   uv run main.py
   ```

2. Clean stored Markdown and rebuild the `doc_chunks` table:

   ```bash
   uv run scripts/migrate_clean_markdown.py
   uv run scripts/create_chunks.py
   ```

3. Embed the chunks and upload them to the Qdrant collection `notion_chunks`:

   ```bash
   uv run scripts/index_qdrant.py
   ```

The indexer adds vectors that are not already present. The `--recreate` option deletes and recreates the collection before indexing:

```bash
uv run scripts/index_qdrant.py --recreate
```

Use `--recreate` only when you intend to replace the existing collection. After crawling updated pages, repeat steps 1–3 to refresh the database and vector index.

## Run the Telegram bot

```bash
uv run src/bot.py
```

Send `/start` for a greeting, then ask a question in text. The bot performs retrieval and answer generation in worker threads so synchronous model and database calls do not block the async event loop. The bot requires `TELEGRAM_BOT_TOKEN`, valid Qdrant settings, and `OPENROUTER_API_KEY`.

## Ask from the command line

```bash
uv run scripts/query_rag.py "How can I get help?"
```

Set the number of retrieved chunks with `--top-k`:

```bash
uv run scripts/query_rag.py --top-k 3 "How can I get help?"
```

## Tests

```bash
uv run pytest
```

## Implementation notes

- The Qdrant collection is named `notion_chunks`; vectors have 1024 dimensions.
- Chunking preserves nearby H2/H3 section context and targets a maximum of 1024 tokens with up to 128 tokens of overlap.
- The answer generator is instructed to use the retrieved knowledge base context and to say when the context does not contain an answer.
- The Telegram handler sends generated answers with HTML formatting and falls back to plain text if Telegram rejects the markup.
