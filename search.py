from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from loader import dp
from database import search_kino_by_title, increment_stat


@dp.message_handler(lambda message: len(message.text) > 2)
async def search_anime(message: types.Message):
    query = message.text.strip()

    # Qidiruv
    results = await search_kino_by_title(query)

    if not results:
        await message.answer("❌ Hech narsa topilmadi.")
        return

    # Javoblar inline tugmalar bilan
    keyboard = InlineKeyboardMarkup(row_width=1)
    for item in results:
        button = InlineKeyboardButton(
            text=f"{item['title']} ({item['code']})",
            url=f"https://t.me/{item['channel']}/{item['message_id']}"
        )
        keyboard.add(button)
        await increment_stat(item['code'], "searched")

    await message.answer("🔍 Natijalar:", reply_markup=keyboard)
