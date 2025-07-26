import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT"))
    )

    async with db_pool.acquire() as conn:
        # Foydalanuvchilar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            );
        """)

        # Kodlar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kino_codes (
                code TEXT PRIMARY KEY,
                channel TEXT,
                message_id INTEGER,
                post_count INTEGER
            );
        """)

        # Statistika jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                code TEXT PRIMARY KEY,
                searched INTEGER DEFAULT 0,
                viewed INTEGER DEFAULT 0
            );
        """)

# === Foydalanuvchi qo‘shish ===
async def add_user(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id
        )

# === Foydalanuvchilar soni ===
async def get_user_count():
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        return row[0]

# === Kod qo‘shish ===
async def add_kino_code(code, channel, message_id, post_count):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO kino_codes (code, channel, message_id, post_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (code) DO UPDATE SET
                channel = EXCLUDED.channel,
                message_id = EXCLUDED.message_id,
                post_count = EXCLUDED.post_count;
        """, code, channel, message_id, post_count)
        await conn.execute("""
            INSERT INTO stats (code) VALUES ($1)
            ON CONFLICT DO NOTHING
        """, code)

# === Kodni olish ===
async def get_kino_by_code(code):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT channel, message_id, post_count FROM kino_codes WHERE code = $1
        """, code)
        return row

# === Barcha kodlarni olish ===
async def get_all_codes():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM kino_codes")
        return rows

# === Kodni o‘chirish ===
async def delete_kino_code(code):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM stats WHERE code = $1", code)
        result = await conn.execute("DELETE FROM kino_codes WHERE code = $1", code)
        return result.endswith("1")

# === Statistika yangilash ===
async def increment_stat(code, field):
    if field not in ("searched", "viewed", "init"):
        return
    async with db_pool.acquire() as conn:
        if field == "init":
            await conn.execute("""
                INSERT INTO stats (code, searched, viewed) VALUES ($1, 0, 0)
                ON CONFLICT DO NOTHING
            """, code)
        else:
            await conn.execute(f"""
                UPDATE stats SET {field} = {field} + 1 WHERE code = $1
            """, code)

# === Barcha statistikani olish (faqat adminlar uchun) ===
async def get_all_stats():
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM stats")

# === Kod statistikasi olish (faqat adminlar uchun) ===
async def get_code_stat(code):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT searched, viewed FROM stats WHERE code = $1", code)

# === Barcha foydalanuvchi IDlarini olish ===
async def get_all_user_ids():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]
