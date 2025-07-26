from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
