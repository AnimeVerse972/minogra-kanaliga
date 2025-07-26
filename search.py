from aiogram import types
from loader import dp
from database import get_all_codes  # yoki alohida qidiruv funksiyasi yozamiz
from asyncpg import Record
from database import db_pool

@dp.message_handler(lambda m: len(m.text) >= 3)  # 3 ta harfdan kam bo'lmasin
async def search_anime(message: types.Message):
    query = message.text.strip().lower()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT code, title FROM kino_codes
            WHERE title ILIKE '%' || $1 || '%'
            LIMIT 10
        """, query)

    if not rows:
        await message.answer("🔍 Hech narsa topilmadi.")
        return

    text = "🔍 Qidiruv natijalari:\n\n"
    for row in rows:
        code = row["code"]
        title = row["title"]
        text += f"🔹 {title} — `{code}`\n"

    await message.answer(text)
