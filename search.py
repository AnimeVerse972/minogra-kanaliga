from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup

from loader import dp
from database import search_kino_by_title, increment_stat


# ==== Holatlar klassi (FSM uchun) ====
class SearchStates(StatesGroup):
    waiting_for_query = State()


# ==== "🔍 Anime qidirish" tugmasi bosilganda ====
@dp.message_handler(Text(equals="🔍 Anime qidirish"))
async def ask_search_query(message: types.Message, state: FSMContext):
    await message.answer("🔎 Qaysi anime kerak? Nomini yozing:")
    await state.set_state(SearchStates.waiting_for_query)


# ==== Foydalanuvchi qidiruv matnini yozganda ====
@dp.message_handler(state=SearchStates.waiting_for_query)
async def handle_search_query(message: types.Message, state: FSMContext):
    query = message.text.strip()

    results = await search_kino_by_title(query)

    if not results:
        await message.answer("❌ Hech narsa topilmadi.")
    else:
        keyboard = InlineKeyboardMarkup(row_width=1)
        for item in results:
            button = InlineKeyboardButton(
                text=f"{item['title']} ({item['code']})",
                url=f"https://t.me/{item['channel']}/{item['message_id']}"
            )
            keyboard.add(button)
            await increment_stat(item['code'], "searched")

        await message.answer("🔍 Topildi:", reply_markup=keyboard)

    await state.finish()
