import asyncpg
import os
import json
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

        # Anime postlar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anime_posts (
                code TEXT PRIMARY KEY,
                title TEXT,
                channel TEXT,
                message_ids JSONB,
                post_count INTEGER
            );
        """)

        # Statistika jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                code TEXT PRIMARY KEY,
                searched INTEGER DEFAULT 0,
                viewed INTEGER DEFAULT 0,
                downloaded INTEGER DEFAULT 0
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

# === Anime post qo‘shish ===
async def add_anime_post(code, title, channel, message_ids, post_count):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO anime_posts (code, title, channel, message_ids, post_count)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                channel = EXCLUDED.channel,
                message_ids = EXCLUDED.message_ids,
                post_count = EXCLUDED.post_count;
        """, code, title, channel, json.dumps(message_ids), post_count)

        await conn.execute("""
            INSERT INTO stats (code) VALUES ($1)
            ON CONFLICT DO NOTHING
        """, code)

# === Kod orqali anime postni olish ===
async def get_kino_by_code(code):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT title, channel, message_ids, post_count FROM anime_posts WHERE code = $1
        """, code)
        return row

# === Barcha anime kodlarini olish ===
async def get_all_anime_codes():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM anime_posts")
        return rows

# === Kodni o‘chirish ===
async def delete_anime_post(code):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM stats WHERE code = $1", code)
        result = await conn.execute("DELETE FROM anime_posts WHERE code = $1", code)
        return result.endswith("1")

# === Statistika yangilash ===
async def increment_stat(code, field):
    if field not in ("searched", "viewed", "downloaded", "init"):
        return
    async with db_pool.acquire() as conn:
        if field == "init":
            await conn.execute("""
                INSERT INTO stats (code, searched, viewed, downloaded)
                VALUES ($1, 0, 0, 0)
                ON CONFLICT DO NOTHING
            """, code)
        else:
            await conn.execute(f"""
                UPDATE stats SET {field} = {field} + 1 WHERE code = $1
            """, code)

# === Barcha statistikani olish ===
async def get_all_stats():
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM stats")

# === Kod statistikasi olish ===
async def get_anime_stat(code):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT searched, viewed, downloaded FROM stats WHERE code = $1
        """, code)

# === Barcha foydalanuvchi IDlarini olish ===
async def get_all_user_ids():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]

async def add_kino_code(code, title, channel, reklama_id, post_count):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute(
        "INSERT INTO kino_posts (code, title, channel, reklama_id, post_count) VALUES ($1, $2, $3, $4, $5)",
        code, title, channel, reklama_id, post_count
    )
    await conn.close()
