import asyncio
import os
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramConflictError
from aiogram.types import FSInputFile

# main.py is NOT modified.
# We import only its existing PDF/data functions.
import main as pdfapp

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Environment Variable topilmadi.")

ACCESS_CODE = os.environ.get("ACCESS_CODE", "2009").strip()

try:
    ACCESS_HOURS = float(os.environ.get("ACCESS_HOURS", "2"))
except ValueError:
    ACCESS_HOURS = 2.0

SESSIONS = {}


def session_active(user_id: int) -> bool:
    expiry = SESSIONS.get(user_id)
    if expiry is None:
        return False

    if datetime.now(timezone.utc) >= expiry:
        SESSIONS.pop(user_id, None)
        return False

    return True


def open_session(user_id: int):
    expiry = datetime.now(timezone.utc) + timedelta(hours=ACCESS_HOURS)
    SESSIONS[user_id] = expiry
    return expiry


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id

    if session_active(user_id):
        await message.answer(
            "✅ Siz allaqachon tizimga kirgansiz.\n\n"
            "Endi 11 qator ma'lumot yuboring."
        )
        return

    await message.answer(
        "🔐 Botga kirish uchun kodni kiriting:\n\n"
        "2009"
    )


@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    # 2009 always starts/restarts a fresh 2-hour session.
    if text == ACCESS_CODE:
        open_session(user_id)
        await message.answer(
            "✅ Muvaffaqiyatli kirdingiz!\n\n"
            f"Bot {ACCESS_HOURS:g} soat faol.\n"
            "Endi ma'lumot yuborishingiz mumkin.\n\n"
            "Muddat tugagach yana 2009 kodini kiriting."
        )
        return

    if not session_active(user_id):
        await message.answer(
            "🔐 Avval kodni kiriting."
        )
        return

    # Existing PDF behavior from main.py.
    output = None
    try:
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        data = pdfapp.build_data(lines)

        output = pdfapp.BASE_DIR / f"confirmation_{user_id}.pdf"
        pdfapp.build_pdf(data, output)

        doc = FSInputFile(output, filename=f"{data['name']}.pdf")
        await message.answer_document(
            doc,
            caption=f"✅ {data['name']} uchun PDF tayyor!"
        )

    except Exception as exc:
        await message.answer(f"❌ Xatolik:\n{exc}")

    finally:
        if output is not None:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass


async def run():
    await bot.delete_webhook(drop_pending_updates=False)

    while True:
        try:
            print("SECURE BOT IS RUNNING")
            print("ACCESS CODE:", ACCESS_CODE)
            print("ACCESS HOURS:", ACCESS_HOURS)

            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types()
            )
            break

        except TelegramConflictError:
            print(
                "TelegramConflictError: another instance is using this bot token. "
                "Stop the old bot instance."
            )
            await asyncio.sleep(10)

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print("Polling error:", exc)
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(run())
