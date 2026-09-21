
import asyncio
import http.server
import os
import threading
from pathlib import Path
from datetime import datetime

import fitz
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageChops
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "template.pdf"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Environment Variable topilmadi.")

# ---------- Web health check ----------
class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Grand Turan bot is active!")

    def log_message(self, fmt, *args):
        return


def run_server():
    port = int(os.environ.get("PORT", "10000"))
    server = http.server.HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


threading.Thread(target=run_server, daemon=True).start()


# ---------- Fonts ----------
REG_FONT = "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Regular.ttf"
BOLD_FONT = "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Bold.ttf"

if Path(REG_FONT).exists():
    pdfmetrics.registerFont(TTFont("RobotoCondensed", REG_FONT))
else:
    REG_FONT = None

if Path(BOLD_FONT).exists():
    pdfmetrics.registerFont(TTFont("RobotoCondensed-Bold", BOLD_FONT))
else:
    BOLD_FONT = None

FONT = "RobotoCondensed" if REG_FONT else "Helvetica"
FONT_BOLD = "RobotoCondensed-Bold" if BOLD_FONT else "Helvetica-Bold"

BLUE = (0.055, 0.337, 0.635)  # close to the template blue
BLACK = (0.08, 0.08, 0.08)
GREEN = (0.0, 0.50, 0.15)


# ---------- Airline logo support ----------
LOGO_URLS = {
    "uzbekistan": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/uzairways.png",
    "uzairways": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/uzairways.png",
    "uzbekistan airways": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/uzairways.png",
    "centrum": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/centrum.png",
    "centrum air": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/centrum.png",
    "fly khiva": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/flykhiva.png",
    "flykhiva": "https://raw.githubusercontent.com/maxpubg2080-ctrl/ticketbot/main/flykhiva.png",
}

def normalize_airline(name: str) -> str:
    n = " ".join(name.lower().strip().split())
    if "fly" in n and "khiva" in n:
        return "fly khiva"
    if "centrum" in n:
        return "centrum air"
    if "uzbekistan" in n or "uzairways" in n or n == "hy":
        return "uzbekistan airways"
    return n


def logo_key(name: str):
    n = normalize_airline(name)
    if "fly khiva" == n:
        return "fly khiva"
    if "centrum" in n:
        return "centrum air"
    if "uzbekistan" in n:
        return "uzbekistan airways"
    return n


def find_local_logo(name: str):
    n = normalize_airline(name)
    candidates = []
    if n == "fly khiva":
        candidates = ["flykhiva.png", "fly_khiva.png"]
    elif n == "centrum air":
        candidates = ["centrum.png", "centrumair.png"]
    elif n == "uzbekistan airways":
        candidates = ["uzairways.png", "uzbekistan.png", "uzairways.jpg"]
    for fname in candidates:
        p = BASE_DIR / fname
        if p.exists():
            return p
    return None


def get_logo(name: str):
    local = find_local_logo(name)
    if local:
        return local

    key = logo_key(name)
    url = LOGO_URLS.get(key)
    if not url:
        return None

    cache_name = {
        "fly khiva": "flykhiva.png",
        "centrum air": "centrum.png",
        "uzbekistan airways": "uzairways.png",
    }.get(key)

    if not cache_name:
        return None

    out = BASE_DIR / cache_name
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        out.write_bytes(r.content)
        return out
    except Exception:
        return None



LOGO_SIZE_TOP = {
    "uzbekistan airways": (130, 30),
    "centrum air": (130, 32),
    "fly khiva": (135, 31),
}
LOGO_SIZE_BOTTOM = {
    "uzbekistan airways": (105, 34),
    "centrum air": (105, 34),
    "fly khiva": (108, 32),
}


def trimmed_logo_path(path: Path):
    """Trim white/transparent margins from a logo for consistent placement."""
    try:
        cache = path.with_name(path.stem + '_trimmed.png')
        if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
            return cache
        img = Image.open(path).convert('RGBA')
        # Make a mask of visible / non-white pixels.
        alpha = img.getchannel('A')
        rgb = img.convert('RGB')
        bg = Image.new('RGB', rgb.size, 'white')
        diff = ImageChops.difference(rgb, bg).convert('L')
        mask = ImageChops.lighter(alpha, diff)
        bbox = mask.getbbox()
        if bbox:
            img = img.crop(bbox)
        img.save(cache)
        return cache
    except Exception:
        return path


# ---------- Input parsing ----------
def parse_datetime_line(line: str):
    parts = line.strip().split()
    if len(parts) < 2:
        raise ValueError(
            "Vaqt qatori noto'g'ri. Masalan: 09:15 23.09.2026"
        )
    time_part = parts[0]
    date_part = parts[-1]
    datetime.strptime(date_part, "%d.%m.%Y")
    if ":" not in time_part:
        raise ValueError(
            "Vaqt qatori noto'g'ri. Masalan: 09:15 23.09.2026"
        )
    return time_part, date_part


def parse_location(value: str):
    value = " ".join(value.strip().split())
    bits = value.split(maxsplit=1)
    if len(bits) >= 2 and len(bits[0]) == 3 and bits[0].isalnum():
        return bits[0].upper(), bits[1]
    return "", value


def clean_baggage(value: str):
    value = value.strip()
    # 30 kg / 30 KG / 30
    return value.upper().replace("KG", "").strip()


def normalize_class(value: str):
    v = value.strip().upper()
    if v.startswith("BUS"):
        return "BUSINESS"
    return "ECONOM"


def build_data(lines):
    if len(lines) not in (11, 12):
        raise ValueError(
            "11 qator yuboring:\n"
            "1 Ism-familiya\n2 Jins\n3 Aviakompaniya\n4 Reys kodi\n"
            "5 Jo'nash joyi\n6 Yetib borish joyi\n7 Uchish vaqt+sanasi\n"
            "8 Yetib borish vaqt+sanasi\n9 ECONOM/BUSINESS\n10 Bagaj\n11 Sana"
        )

    # Yangi format:
    # 0 name
    # 1 gender
    # 2 airline
    # 3 flight code
    # 4 from
    # 5 to
    # 6 dep datetime
    # 7 arr datetime
    # 8 class
    # 9 baggage
    # 10 tour date

    name = lines[0].strip()
    gender = lines[1].strip().upper()
    airline = lines[2].strip()
    flight_code = lines[3].strip().upper()
    from_code, from_city = parse_location(lines[4])
    to_code, to_city = parse_location(lines[5])
    dep_time, dep_date = parse_datetime_line(lines[6])
    arr_time, arr_date = parse_datetime_line(lines[7])
    travel_class = normalize_class(lines[8])
    baggage = clean_baggage(lines[9])
    tour_date = lines[10].strip()

    # Sana to'g'ri formatda ekanini tekshiramiz.
    datetime.strptime(tour_date, "%d.%m.%Y")

    return {
        "name": name,
        "gender": gender,
        "airline": airline,
        "flight_code": flight_code,
        "from_code": from_code,
        "from_city": from_city,
        "to_code": to_code,
        "to_city": to_city,
        "dep_time": dep_time,
        "dep_date": dep_date,
        "arr_time": arr_time,
        "arr_date": arr_date,
        "travel_class": travel_class,
        "baggage": baggage,
        "tour_date": tour_date,
    }


# ---------- PDF generation ----------
def make_overlay(data, overlay_path: Path):
    W, H = 596, 843
    c = canvas.Canvas(str(overlay_path), pagesize=(W, H))

    def txt(x, top_y, s, size=9, color=BLACK, bold=False, align="left"):
        c.setFont(FONT_BOLD if bold else FONT, size)
        c.setFillColorRGB(*color)
        y = H - top_y
        if align == "center":
            c.drawCentredString(x, y, str(s))
        elif align == "right":
            c.drawRightString(x, y, str(s))
        else:
            c.drawString(x, y, str(s))

    # Dynamic airline logo in the top-right header area.
    # The base template already has Grand Turan on the left and the underline;
    # only the logo slot is covered and replaced here.
    c.setFillColorRGB(1, 1, 1)
    c.rect(382, H - 68, 172, 47, stroke=0, fill=1)
    logo = get_logo(data["airline"])
    if logo:
        try:
            logo_path = trimmed_logo_path(logo)
            img = ImageReader(str(logo_path))
            iw, ih = img.getSize()
            max_w, max_h = LOGO_SIZE_TOP.get(logo_key(data["airline"]), (130, 30))
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(img, 505 - dw/2, H - 48 - dh/2, width=dw, height=dh, mask='auto', preserveAspectRatio=True)
        except Exception:
            txt(505, 49, data["airline"].upper(), 8.5, BLACK, True, "center")
    else:
        txt(505, 49, data["airline"].upper(), 8.5, BLACK, True, "center")

    # Top blue info box
    txt(110, 217, data["tour_date"], 9.7)
    route = f'{data["from_city"]} - {data["to_city"]} (Aviabilet)'
    txt(124, 238, route, 9.6)

    # Manager name and phone are static in template.pdf and intentionally untouched.

    # Passenger row
    txt(120, 352, data["name"], 9.4, BLUE, True)
    txt(484, 352, "MR" if data["gender"] in {"M", "MALE", "MR", "ERKAK"} else "MRS",
        9.4, BLUE, True, "center")

    # Bottom airline logo in the Aviation Company cell.
    # Cell is blank in template, so the logo is fully dynamic.
    if logo:
        try:
            img = ImageReader(str(trimmed_logo_path(logo)))
            iw, ih = img.getSize()
            max_w, max_h = LOGO_SIZE_BOTTOM.get(logo_key(data["airline"]), (105, 34))
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(img, 113 - dw/2, H - 460 - dh/2, width=dw, height=dh, mask='auto', preserveAspectRatio=True)
        except Exception:
            txt(113, 468, data["airline"].upper(), 8.4, BLACK, True, "center")
    else:
        txt(113, 468, data["airline"].upper(), 8.4, BLACK, True, "center")

    txt(113, 497, data["flight_code"], 9.6, BLUE, True, "center")

    # Departure
    if data["from_code"]:
        txt(242, 474, data["from_code"], 15, BLUE, True, "center")
    txt(242, 495, data["from_city"], 9.4, BLACK, True, "center")
    txt(242, 511, f'{data["dep_time"]} - {data["dep_date"]}', 9.0, BLACK, False, "center")

    # Arrival
    if data["to_code"]:
        txt(381, 474, data["to_code"], 15, BLUE, True, "center")
    txt(381, 495, data["to_city"], 9.4, BLACK, True, "center")
    txt(381, 511, f'{data["arr_time"]} - {data["arr_date"]}', 9.0, BLACK, False, "center")

    # Class / baggage
    txt(496, 486, data["travel_class"], 9.6, BLUE, True, "center")
    txt(496, 506, f'{data["baggage"]} KG Bagaj', 8.8, GREEN, True, "center")

    c.save()

def build_pdf(data, output_path: Path):
    if not TEMPLATE.exists():
        raise FileNotFoundError("template.pdf topilmadi.")

    overlay_path = output_path.with_suffix(".overlay.pdf")
    make_overlay(data, overlay_path)

    base = fitz.open(str(TEMPLATE))
    overlay = fitz.open(str(overlay_path))
    base[0].show_pdf_page(base[0].rect, overlay, 0)
    base.save(str(output_path), garbage=4, deflate=True)
    base.close()
    overlay.close()
    overlay_path.unlink(missing_ok=True)


# ---------- Telegram ----------
bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Salom!\n\n"
        "11 qator yuboring:\n"
        "Ism-familiya\n"
        "MR/MRS\n"
        "Uzbekistan Airways / Centrum Air / Fly Khiva\n"
        "HY341\n"
        "TAS Tashkent\n"
        "SSH Sharm El Sheikh\n"
        "09:15 23.09.2026\n"
        "13:05 23.09.2026\n"
        "ECONOM yoki BUSINESS\n"
        "30 kg\n"
        "23.09.2026"
    )


@dp.message(F.text)
async def handle_text(message: types.Message):
    try:
        lines = [x.strip() for x in message.text.splitlines() if x.strip()]
        data = build_data(lines)

        output = BASE_DIR / f'confirmation_{message.from_user.id}.pdf'
        build_pdf(data, output)

        doc = FSInputFile(output, filename=f"{data['name']}.pdf")
        await message.answer_document(
            doc,
            caption=f"✅ {data['name']} uchun PDF tayyor!"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik:\n{e}")
    finally:
        try:
            output.unlink(missing_ok=True)
        except Exception:
            pass


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
