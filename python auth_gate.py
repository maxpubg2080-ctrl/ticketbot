import asyncio
import os
from datetime import datetime, timedelta, timezone

from aiogram import BaseMiddleware
from aiogram.types import Message

# This file adds a 2-hour access gate WITHOUT modifying main.py.
# Render should run this file instead of main.py:
#     python auth_gate.py
#
# Default access code: 2009
# Default access duration: 2 hours
# Optional environment variables:
#   ACCESS_CODE=2009
#   ACCESS_HOURS=2

ACCESS_CODE = os.getenv("ACCESS_CODE", "2009").strip()
try:
    ACCESS_HOURS = float(os.getenv("ACCESS_HOURS", "2"))
except ValueError:
    ACCESS_HOURS = 2.0

# Telegram user_id -> access expiration time (UTC)
access_until = {}


def is_active(user_id: int) -> bool:
    expires = access_until.get(user_id)
    if expires is None:
        return False

    now = datetime.now(timezone.utc)
    if now >= expires:
        access_until.pop(user_id, None)
        return False

    return True


def activate(user_id: int) -> datetime:
    expires = datetime.now(timezone.utc) + timedelta(hours=ACCESS_HOURS)
    access_until[user_id] = expires
    return expires


class AccessGateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if user is None:
            return await handler(event, data)

        user_id = user.id
        text = (event.text or "").strip()

        # /start: ask for the code unless this user already has an active session.
        if text.startswith("/start"):
            if is_active(user_id):
                return await handler(event, data)

            await event.answer(
                "🔐 Botga kirish uchun kodni kiriting:\n\n"
                "Kod: 2009\n"
                "To'g'ri kod kiritilgandan keyin bot 2 soat ishlaydi."
            )
            return

        # Entering 2009 always starts/restarts a fresh 2-hour session.
        if text == ACCESS_CODE:
            activate(user_id)
            hours_text = (
                str(int(ACCESS_HOURS))
                if ACCESS_HOURS.is_integer()
                else str(ACCESS_HOURS)
            )

            await event.answer(
                "✅ Muvaffaqiyatli kirdingiz!\n\n"
                f"Bot {hours_text} soat faol.\n"
                "Endi ma'lumot yuborishingiz mumkin.\n\n"
                "⏳ Muddat tugagach, yana 2009 kodini kiriting."
            )
            return

        # Expired/not logged in: block all other messages.
        if not is_active(user_id):
            await event.answer(
                "🔐 Kod kerak.\n\n"
                "Botdan foydalanish uchun 2009 kodini kiriting."
            )
            return

        # Active session: preserve all existing main.py behaviour unchanged.
        return await handler(event, data)


async def run():
    # Import main.py without running its polling block.
    import main as app

    # Gate incoming Telegram messages before main.py's existing handlers.
    app.dp.message.outer_middleware(AccessGateMiddleware())

    # Start the original bot unchanged.
    await app.main()


if __name__ == "__main__":
    asyncio.run(run())
