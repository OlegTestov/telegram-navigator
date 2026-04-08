"""Generate Telegram String Session for Telethon.

Run this script locally (requires interactive phone + OTP input).
Copy the resulting session string into your .env file as TELEGRAM_SESSION_STRING.
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")


async def main():
    print("Generating Telegram String Session...\n")
    print("You will need to:")
    print("  1. Enter your phone number")
    print("  2. Enter the code sent to Telegram")
    print("  3. Copy the resulting session string\n")

    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_string = client.session.save()
        print("\n" + "=" * 60)
        print("Session string:")
        print("=" * 60)
        print(session_string)
        print("=" * 60)
        print(f"\nAdd to your .env file:")
        print(f"TELEGRAM_SESSION_STRING={session_string}")


if __name__ == "__main__":
    asyncio.run(main())
