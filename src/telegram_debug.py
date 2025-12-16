from telethon import TelegramClient 
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
TELETHON_SESSION_NAME = os.getenv('TELETHON_SESSION_NAME')

telegram_client = TelegramClient(TELETHON_SESSION_NAME, API_ID, API_HASH)

async def Main():
    me = await telegram_client.get_me()
    print(me)

if __name__ == "__main__":
    asyncio.run(Main())
