"""Script to test Telegram Markdown/HTML links and formatting options."""

import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from .env")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Напишите любое сообщение, и я пришлю варианты оформления ссылок!")


@dp.message()
async def handle_message(message: types.Message):
    # Вариант 1: Кликабельные текстовые ссылки (Markdown)
    variant_1 = (
        "<b>Вариант 1: Кликабельный текст (Markdown)</b>\n\n"
        "По закону вы имеете право на АГС. Подробнее читайте в "
        "[памятке Идите Лесом](https://www.iditelesombase.org/p/b25165733abe44d4874cf8f0ff63e486).\n\n"
        "Если пришла повестка, изучите [инструкцию по повесткам](https://t.me/iditelesom_info_bot)."
    )

    # Вариант 2: Полноценные прямые URL в конце предложения
    variant_2 = (
        "<b>Вариант 2: Прямые ссылки URL</b>\n\n"
        "По закону вы имеете право на АГС. Подробная памятка:\n"
        "https://www.iditelesombase.org/p/b25165733abe44d4874cf8f0ff63e486\n\n"
        "Бот поддержки: https://t.me/iditelesom_info_bot"
    )

    # Вариант 3: Список источников в самом конце ответа (Footnotes)
    variant_3 = (
        "<b>Вариант 3: Сноски в конце ответа (Чистый текст + Источники)</b>\n\n"
        "Вы имеете право на замену службы по призыву на альтернативную гражданскую службу (АГС). "
        "Для этого необходимо заранее подать заявление в военкомат.\n\n"
        "<b>Источники:</b>\n"
        "1. <a href='https://www.iditelesombase.org/p/b25165733abe44d4874cf8f0ff63e486'>Инструкция по АГС</a>\n"
        "2. <a href='https://t.me/iditelesom_info_bot'>Бот консультаций</a>"
    )

    # Отправляем все варианты
    await message.answer(variant_1, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    await message.answer(variant_2, disable_web_page_preview=True)
    await message.answer(variant_3, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))