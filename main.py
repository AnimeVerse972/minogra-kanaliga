from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import init_db, add_user, get_user_count, save_anime_post, add_kino_code, get_anime_by_code, get_all_codes, delete_kino_code, get_code_stat, increment_stat, get_all_user_ids
import os

# === YUKLAMALAR ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNELS = os.getenv("CHANNEL_USERNAMES").split(",")
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

async def make_subscribe_markup(code):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel in CHANNELS:
        try:
            invite_link = await bot.create_chat_invite_link(channel.strip())
            keyboard.add(InlineKeyboardButton("📢 Obuna bo‘lish", url=invite_link.invite_link))
        except Exception as e:
            print(f"❌ Link yaratishda xatolik: {channel} -> {e}")
    keyboard.add(InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}"))
    return keyboard

ADMINS = [6486825926,8017776953]

# === HOLATLAR ===
class AdminStates(StatesGroup):
    waiting_for_delete_code = State()
    waiting_for_stat_code = State()
    waiting_for_broadcast_data = State()

class AddAnimeFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_code = State()
    waiting_for_posts = State()

@dp.message_handler(lambda msg: msg.text == "➕ Anime qo‘shish", user_id=ADMINS)
async def start_add_anime(message: types.Message):
    await message.answer("🎬 Iltimos, animening nomini yuboring:")
    await AddAnimeFSM.waiting_for_title.set()

@dp.message_handler(state=AddAnimeFSM.waiting_for_title)
async def get_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("🔢 Endi animening kodini yuboring:")
    await AddAnimeFSM.waiting_for_code.set()

@dp.message_handler(state=AddAnimeFSM.waiting_for_code)
async def get_code(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❗ Kod faqat raqam bo‘lishi kerak.")
    await state.update_data(code=message.text)
    await state.update_data(posts=[])
    await message.answer("📤 Endi postlarni yuboring (video, fayl, matn...). Tugagach, /saqlash deb yozing.")
    await AddAnimeFSM.waiting_for_posts.set()

@dp.message_handler(state=AddAnimeFSM.waiting_for_posts, content_types=types.ContentTypes.ANY)
async def collect_posts(message: types.Message, state: FSMContext):
    data = await state.get_data()
    posts = data.get("posts", [])
    posts.append(message)
    await state.update_data(posts=posts)
    await message.answer(f"✅ Post qabul qilindi. Hozircha {len(posts)} ta post. Davom eting yoki /saqlash deb yozing.")

@dp.message_handler(commands=["saqlash"], state=AddAnimeFSM.waiting_for_posts)
async def finalize_anime(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data["title"]
    code = data["code"]
    posts = data["posts"]

    if not posts:
        return await message.answer("❗ Postlar yo‘q. Avval postlarni yuboring.")

    save_channel = os.getenv("SAVE_CHANNEL")
    main_channel = os.getenv("MAIN_CHANNEL")
    bot_username = os.getenv("BOT_USERNAME").replace("@", "")

    saved_ids = []

    for post in posts:
        try:
            msg = await bot.copy_message(save_channel, post.chat.id, post.message_id)
            saved_ids.append(msg.message_id)
        except Exception as e:
            print(f"Postni saqlab bo‘lmadi: {e}")

    if not saved_ids:
        return await message.answer("❌ Hech qanday post saqlanmadi.")

    # 1-postni asosiy kanalga yuborish
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📥 Yuklab olish", url=f"https://t.me/{bot_username}?start={code}")
    )
    sent_main = await bot.copy_message(main_channel, save_channel, saved_ids[0], reply_markup=keyboard)

    # SQLga saqlash
    await save_anime_post(code, title, ",".join(map(str, saved_ids)), sent_main.message_id)
    await message.answer("✅ Anime muvaffaqiyatli saqlandi!")
    await state.finish()

@dp.message_handler(lambda msg: msg.text.startswith("/start"))
async def handle_start(message: types.Message):
    args = message.get_args()
    if not args.isdigit():
        return await message.answer("👋 Assalomu alaykum!")
    
    code = args
    data = await get_anime_by_code(code)
    if not data:
        return await message.answer("❌ Kod topilmadi.")

    post_ids = list(map(int, data["message_ids"].split(",")))
    for pid in post_ids:
        try:
            await bot.copy_message(message.chat.id, os.getenv("SAVE_CHANNEL"), pid)
        except:
            pass


# === OBUNA TEKSHIRISH ===
async def is_user_subscribed(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel.strip(), user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"❗ Obuna tekshirishda xatolik: {channel} -> {e}")
            return False
    return True

# === /start ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)

    args = message.get_args()
    if args and args.isdigit():
        code = args
        if not await is_user_subscribed(message.from_user.id):
            markup = await make_subscribe_markup(code)
            await message.answer("❗ Kino olishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:", reply_markup=markup)
        else:
            await send_reklama_post(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
        kb.add("📊 Statistika", "📈 Kod statistikasi")
        kb.add("📢 Habar yuborish", "❌ Kodni o‘chirish")
        kb.add("❌ Bekor qilish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        await message.answer("🎬 Botga xush kelibsiz!\nKod kiriting:")

# === Kod statistikasi
@dp.message_handler(lambda m: m.text == "📈 Kod statistikasi")
async def ask_stat_code(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("📥 Kod raqamini yuboring:")
    await AdminStates.waiting_for_stat_code.set()

@dp.message_handler(state=AdminStates.waiting_for_stat_code)
async def show_code_stat(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    if not code:
        await message.answer("❗ Kod yuboring.")
        return
    stat = await get_code_stat(code)
    if not stat:
        await message.answer("❗ Bunday kod statistikasi topilmadi.")
        return

    await message.answer(
        f"📊 <b>{code} statistikasi:</b>\n"
        f"🔍 Qidirilgan: <b>{stat['searched']}</b>\n"
        f"👁 Ko‘rilgan: <b>{stat['viewed']}</b>",
        parse_mode="HTML"
    )

# === Oddiy raqam yuborilganda
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    if not await is_user_subscribed(message.from_user.id):
        markup = await make_subscribe_markup(code)
        await message.answer("❗ Kino olishdan oldin quyidagi kanal(lar)ga obuna bo‘ling:", reply_markup=markup)
    else:
        await increment_stat(code, "init")
        await increment_stat(code, "searched")
        await send_reklama_post(message.from_user.id, code)
        await increment_stat(code, "viewed")

# === Obuna tekshirish callback
@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub_callback(callback_query: types.CallbackQuery):
    code = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id

    not_subscribed = []
    buttons = []

    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append(channel)
                invite_link = await bot.create_chat_invite_link(channel)
                buttons.append([
                    InlineKeyboardButton("🔔 Obuna bo‘lish", url=invite_link.invite_link)
                ])
        except Exception as e:
            print(f"❌ Obuna tekshiruv xatosi: {channel} -> {e}")
            continue

    if not_subscribed:
        buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback_query.message.edit_text(
            "❗ Hali ham barcha kanallarga obuna bo‘lmagansiz. Iltimos, barchasiga obuna bo‘ling:",
            reply_markup=keyboard
        )
    else:
        await callback_query.message.edit_text("✅ Obuna muvaffaqiyatli tekshirildi!")
        await send_reklama_post(user_id, code)

# === Reklama postni yuborish
async def send_reklama_post(user_id, code):
    data = await get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "❌ Kod topilmadi.")
        return

    channel, reklama_id, post_count = data["channel"], data["message_id"], data["post_count"]

    buttons = [InlineKeyboardButton(str(i), callback_data=f"kino:{code}:{i}") for i in range(1, post_count + 1)]
    keyboard = InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)

    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except:
        await bot.send_message(user_id, "❌ Reklama postni yuborib bo‘lmadi.")

# === Tugma orqali kino yuborish
@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)

    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]

    if number > post_count:
        await callback.answer("❌ Bunday post yo‘q!", show_alert=True)
        return

    await bot.copy_message(callback.from_user.id, channel, base_id + number - 1)
    await callback.answer()


# === 📢 Habar yuborish
@dp.message_handler(lambda m: m.text == "📢 Habar yuborish")
async def ask_broadcast_info(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await AdminStates.waiting_for_broadcast_data.set()
    await message.answer("📨 Habar yuborish uchun format:\n`@kanal xabar_id`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_broadcast_data)
async def send_forward_only(message: types.Message, state: FSMContext):
    await state.finish()
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❗ Format noto‘g‘ri. Masalan: `@kanalim 123`")
        return

    channel_username, msg_id = parts
    if not msg_id.isdigit():
        await message.answer("❗ Xabar ID raqam bo‘lishi kerak.")
        return

    msg_id = int(msg_id)
    users = await get_all_user_ids()  # Foydalanuvchilar ro‘yxati

    success = 0
    fail = 0

    for user_id in users:
        try:
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=channel_username,
                message_id=msg_id
            )
            success += 1
        except Exception as e:
            print(f"Xatolik {user_id} uchun: {e}")
            fail += 1

    await message.answer(f"✅ Yuborildi: {success} ta\n❌ Xatolik: {fail} ta")



# === Kodlar ro‘yxati
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def kodlar(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("📂 Kodlar yo‘q.")
        return
    text = "📄 Kodlar:\n"
    for row in kodlar:
        code, ch, msg_id, count = row["code"], row["channel"], row["message_id"], row["post_count"]
        text += f"🔹 {code} → {ch} | {msg_id} ({count} post)\n"
    await message.answer(text)

# === Statistika
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    kodlar = await get_all_codes()
    foydalanuvchilar = await get_user_count()
    await message.answer(f"📦 Kodlar: {len(kodlar)}\n👥 Foydalanuvchilar: {foydalanuvchilar}")

# === ❌ Kodni o‘chirish
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def ask_delete_code(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_delete_code.set()
        await message.answer("🗑 Qaysi kodni o‘chirmoqchisiz? Kodni yuboring.")

@dp.message_handler(state=AdminStates.waiting_for_delete_code)
async def delete_code_handler(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto‘g‘ri format. Kod raqamini yuboring.")
        return
    deleted = await delete_kino_code(code)
    if deleted:
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Kod topilmadi yoki o‘chirib bo‘lmadi.")

# === Bekor qilish
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
    kb.add("📊 Statistika", "📈 Kod statistikasi")
    kb.add("📢 Habar yuborish", "❌ Kodni o‘chirish")
    kb.add("❌ Bekor qilish")
    await message.answer("❌ Bekor qilindi", reply_markup=kb)

# === START ===
async def on_startup(dp):
    await init_db()
    print("✅ PostgreSQL bazaga ulandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
