import asyncio
import http.server
import os
import re
import threading
from pathlib import Path

import fitz  # PyMuPDF
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile


# =========================
# Render / UptimeRobot server
# =========================
class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

    def log_message(self, fmt, *args):
        pass


def run_server():
    port = int(os.environ.get("PORT", "10000"))
    httpd = http.server.HTTPServer(("", port), HealthCheckHandler)
    httpd.serve_forever()


threading.Thread(target=run_server, daemon=True).start()


# =========================
# Configuration
# =========================
BASE_DIR = Path(__file__).resolve().parent

# Put your finished Grand Turan PDF here and name it template.pdf
TEMPLATE_CANDIDATES = [
    BASE_DIR / "template.pdf",
    BASE_DIR / "Grand_Turan_Confirmation_FULL_EDITABLE_FINAL.pdf",
]

LOGO_FILES = {
    "flykhiva": [BASE_DIR / "flykhiva.png", BASE_DIR / "fly khiva.png"],
    "centrum": [BASE_DIR / "centrum.png", BASE_DIR / "centrumair.png"],
    "uzairways": [BASE_DIR / "uzairways.png", BASE_DIR / "uzbekistan.png"],
}

# Set these in Render Environment Variables instead of putting the token in GitHub.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MANAGER_NAME = os.getenv("MANAGER_NAME", "SHAMSIDDIN").strip()
MANAGER_PHONE = os.getenv("MANAGER_PHONE", "+998 77 393 57 57").strip()

# Template colors
BLUE = (15 / 255, 76 / 255, 129 / 255)
DARK_BLUE = (40 / 255, 72 / 255, 120 / 255)
GREEN = (22 / 255, 145 / 255, 83 / 255)
WHITE = (1, 1, 1)
LIGHT_BLUE = (235 / 255, 246 / 255, 252 / 255)

# Common airport aliases. Input may also already contain the 3-letter code.
CITY_CODES = {
    "tashkent": "TAS",
    "toshkent": "TAS",
    "sharm el sheikh": "SSH",
    "sharm": "SSH",
    "dubai": "DXB",
    "istanbul": "IST",
    "cairo": "CAI",
    "almaty": "ALA",
    "astana": "NQZ",
    "shymkent": "CIT",
    "moscow": "MOW",
    "jeddah": "JED",
    "medina": "MED",
    "madina": "MED",
}


def find_template() -> Path:
    for path in TEMPLATE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "template.pdf topilmadi. Grand Turan PDF faylingizni repo ichiga template.pdf nomi bilan yuklang."
    )


def find_logo(kind: str) -> Path | None:
    for path in LOGO_FILES.get(kind, []):
        if path.exists():
            return path
    return None


def normalize_airline(value: str) -> str:
    v = value.strip().lower().replace("_", " ")
    v = re.sub(r"\s+", " ", v)

    if "fly khiva" in v or "flykhiva" in v or "khiva" in v:
        return "flykhiva"
    if "centrum" in v:
        return "centrum"
    if "uzbekistan airways" in v or "uzairways" in v or v == "uzbekistan":
        return "uzairways"
    return "unknown"


def airline_label(key: str, original: str) -> str:
    return {
        "flykhiva": "FLY KHIVA",
        "centrum": "CENTRUM AIR",
        "uzairways": "UZBEKISTAN AIRWAYS",
    }.get(key, original.upper())


def parse_airport(value: str) -> tuple[str, str]:
    """Accepts 'TAS Tashkent', 'SSH Sharm El Sheikh', or just a city name."""
    v = value.strip()
    m = re.match(r"^([A-Za-z]{3})\s+(.+)$", v)
    if m:
        return m.group(1).upper(), m.group(2).strip()

    code = CITY_CODES.get(v.lower())
    if code:
        return code, v

    return "", v


def normalize_class(value: str) -> str:
    v = value.strip().lower()
    if v in {"econom", "economic", "economy", "eko", "eco"}:
        return "ECONOM"
    if v in {"business", "biznes", "biz"}:
        return "BUSINESS"
    return value.strip().upper()


def normalize_baggage(value: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", "."))
    if not m:
        return value.strip().upper()
    number = m.group(1).rstrip("0").rstrip(".") if "." in m.group(1) else m.group(1)
    return f"{number} KG Bagaj"


def split_time_and_date(value: str, fallback_date: str) -> tuple[str, str]:
    """Accept '09:15 23.09.2026' or just '09:15'."""
    m = re.match(r"^\s*(\d{1,2}:\d{2})(?:\s+(.+))?\s*$", value.strip())
    if not m:
        return value.strip(), fallback_date
    return m.group(1), (m.group(2).strip() if m.group(2) else fallback_date)


def parse_message(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # New format (11 lines):
    # 0 name
    # 1 gender
    # 2 airline
    # 3 flight code
    # 4 from
    # 5 to
    # 6 departure time/date
    # 7 arrival time/date
    # 8 class
    # 9 baggage
    # 10 document date
    if len(lines) == 11:
        data = {
            "name": lines[0],
            "gender": lines[1],
            "airline": lines[2],
            "flight_code": lines[3],
            "from_raw": lines[4],
            "to_raw": lines[5],
            "dep_raw": lines[6],
            "arr_raw": lines[7],
            "service_class": normalize_class(lines[8]),
            "baggage": normalize_baggage(lines[9]),
            "date": lines[10],
        }
        return enrich_data(data)

    # Backward-compatible old format (12 lines):
    # name, gender, passport, birth_date, airline, flight, from, to, dep, arr, baggage, date
    if len(lines) >= 12:
        data = {
            "name": lines[0],
            "gender": lines[1],
            "airline": lines[4],
            "flight_code": lines[5],
            "from_raw": lines[6],
            "to_raw": lines[7],
            "dep_raw": lines[8],
            "arr_raw": lines[9],
            "service_class": "ECONOM",
            "baggage": normalize_baggage(lines[10]),
            "date": lines[11],
        }
        return enrich_data(data)

    raise ValueError(
        "11 qator yuboring:\n"
        "ISM FAMILIYA\nMR/MRS\nAIRLINE\nFLIGHT CODE\nTAS Tashkent\nSSH Sharm El Sheikh\n"
        "09:15 23.09.2026\n13:05 23.09.2026\nECONOM yoki BUSINESS\n30 kg\n23.09.2026"
    )


def enrich_data(data: dict) -> dict:
    dep_code, dep_city = parse_airport(data["from_raw"])
    arr_code, arr_city = parse_airport(data["to_raw"])
    dep_time, dep_date = split_time_and_date(data["dep_raw"], data["date"])
    arr_time, arr_date = split_time_and_date(data["arr_raw"], data["date"])

    data.update(
        {
            "airline_key": normalize_airline(data["airline"]),
            "airline_label": airline_label(normalize_airline(data["airline"]), data["airline"]),
            "dep_code": dep_code,
            "dep_city": dep_city,
            "arr_code": arr_code,
            "arr_city": arr_city,
            "dep_time": dep_time,
            "arr_time": arr_time,
            "dep_date": dep_date,
            "arr_date": arr_date,
        }
    )
    return data


def add_text(page, rect, text, *, fontsize, color=BLUE, align=0, bold=False, fill=None):
    """Insert replacement text in a fixed rectangle."""
    if fill is not None:
        page.draw_rect(rect, color=None, fill=fill, overlay=True)

    font = "hebo" if bold else "helv"
    # Give a little room and let PyMuPDF clip/fit inside the original cell.
    page.insert_textbox(
        rect,
        str(text),
        fontsize=fontsize,
        fontname=font,
        color=color,
        align=align,
        overlay=True,
    )


def cover_text(page, rect, fill):
    page.draw_rect(rect, color=None, fill=fill, overlay=True)


def fit_logo_rect(image_path: Path, box: fitz.Rect, pad=2.0) -> fitz.Rect:
    """Fit an image inside box without distorting aspect ratio."""
    pix = fitz.Pixmap(str(image_path))
    iw, ih = pix.width, pix.height
    if iw <= 0 or ih <= 0:
        return box

    avail_w = max(1, box.width - 2 * pad)
    avail_h = max(1, box.height - 2 * pad)
    scale = min(avail_w / iw, avail_h / ih)
    w, h = iw * scale, ih * scale
    x0 = box.x0 + (box.width - w) / 2
    y0 = box.y0 + (box.height - h) / 2
    return fitz.Rect(x0, y0, x0 + w, y0 + h)


def replace_flight_logo(page, airline_key: str, original_label: str):
    # Existing template flight logo area.
    logo_box = fitz.Rect(68, 458.08, 158, 479.92)
    page.draw_rect(logo_box, color=None, fill=WHITE, overlay=True)

    logo_path = find_logo(airline_key)
    if logo_path:
        page.insert_image(fit_logo_rect(logo_path, logo_box), filename=str(logo_path), overlay=True)
        return

    # Fallback if the logo file is not uploaded to GitHub/Render.
    fallback = airline_label(airline_key, original_label)
    add_text(page, logo_box, fallback, fontsize=8.5, color=DARK_BLUE, align=1, bold=True)


def build_pdf(data: dict, output_path: Path):
    template = find_template()
    doc = fitz.open(str(template))
    page = doc[0]

    # Template is A4 and these are the dynamic text boxes from the supplied PDF.
    # We cover only the existing dynamic text, leaving the design, borders and logos intact.

    # Sana / date in the blue info box.
    date_rect = fitz.Rect(104, 204, 158, 222)
    cover_text(page, date_rect, LIGHT_BLUE)
    add_text(page, date_rect, data["date"], fontsize=10.8, color=DARK_BLUE)

    # Route in the blue info box.
    route_rect = fitz.Rect(106, 224, 286, 242)
    cover_text(page, route_rect, LIGHT_BLUE)
    route_text = f"{data['dep_city']} - {data['arr_city']} (Aviabilet)"
    add_text(page, route_rect, route_text, fontsize=10.6, color=DARK_BLUE)

    # Manager block.
    mgr_name_rect = fitz.Rect(430, 212, 505, 234)
    cover_text(page, mgr_name_rect, WHITE)
    add_text(page, mgr_name_rect, MANAGER_NAME, fontsize=11.8, color=DARK_BLUE, align=1, bold=True)

    mgr_phone_rect = fitz.Rect(425, 233, 510, 251)
    cover_text(page, mgr_phone_rect, WHITE)
    add_text(page, mgr_phone_rect, MANAGER_PHONE, fontsize=10.1, color=(29/255, 64/255, 150/255), align=1, bold=True)

    # Passenger name / gender.
    name_rect = fitz.Rect(107, 336, 455, 356)
    cover_text(page, name_rect, WHITE)
    add_text(page, name_rect, data["name"], fontsize=10.8, color=DARK_BLUE, bold=True)

    gender_rect = fitz.Rect(466, 336, 500, 356)
    cover_text(page, gender_rect, WHITE)
    gender = data["gender"].upper()
    if gender in {"M", "MALE", "ERKAK", "MR"}:
        gender = "MR"
    elif gender in {"F", "FEMALE", "AYOL", "MRS", "MS"}:
        gender = "MRS"
    add_text(page, gender_rect, gender, fontsize=10.8, color=DARK_BLUE, align=1, bold=True)

    # Flight code.
    code_rect = fitz.Rect(90, 487, 135, 507)
    cover_text(page, code_rect, WHITE)
    add_text(page, code_rect, data["flight_code"], fontsize=10.8, color=(29/255, 64/255, 150/255), align=1, bold=True)

    # Airline logo inside the flight table.
    replace_flight_logo(page, data["airline_key"], data["airline"])

    # Departure code / city / time.
    dep_code_rect = fitz.Rect(224, 458, 264, 484)
    cover_text(page, dep_code_rect, WHITE)
    add_text(page, dep_code_rect, data["dep_code"], fontsize=18, color=(29/255, 92/255, 220/255), align=1, bold=True)

    dep_city_rect = fitz.Rect(195, 482, 283, 502)
    cover_text(page, dep_city_rect, WHITE)
    add_text(page, dep_city_rect, data["dep_city"], fontsize=10.5, color=DARK_BLUE, align=1, bold=True)

    dep_time_rect = fitz.Rect(197, 498, 283, 513)
    cover_text(page, dep_time_rect, WHITE)
    dep_datetime = f"{data['dep_time']} - {data['dep_date']}"
    add_text(page, dep_time_rect, dep_datetime, fontsize=9.6, color=DARK_BLUE, align=1, bold=True)

    # Arrival code / city / time.
    arr_code_rect = fitz.Rect(362, 458, 402, 484)
    cover_text(page, arr_code_rect, WHITE)
    add_text(page, arr_code_rect, data["arr_code"], fontsize=18, color=(29/255, 92/255, 220/255), align=1, bold=True)

    arr_city_rect = fitz.Rect(338, 482, 421, 502)
    cover_text(page, arr_city_rect, WHITE)
    add_text(page, arr_city_rect, data["arr_city"], fontsize=10.3, color=DARK_BLUE, align=1, bold=True)

    arr_time_rect = fitz.Rect(338, 498, 422, 513)
    cover_text(page, arr_time_rect, WHITE)
    arr_datetime = f"{data['arr_time']} - {data['arr_date']}"
    add_text(page, arr_time_rect, arr_datetime, fontsize=9.6, color=DARK_BLUE, align=1, bold=True)

    # Class and baggage.
    class_rect = fitz.Rect(470, 470, 526, 489)
    cover_text(page, class_rect, WHITE)
    add_text(page, class_rect, data["service_class"], fontsize=10.8, color=(29/255, 64/255, 150/255), align=1, bold=True)

    bag_rect = fitz.Rect(468, 491, 528, 511)
    cover_text(page, bag_rect, WHITE)
    add_text(page, bag_rect, data["baggage"], fontsize=9.8, color=GREEN, align=1, bold=True)

    # Save as a fresh PDF.
    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()


# =========================
# Telegram bot
# =========================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Render Environment Variable sifatida berilmagan.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Salom! 11 qator yuboring:\n\n"
        "SAIDOV SHOKHRUKH\n"
        "MR\n"
        "Uzbekistan Airways\n"
        "HY341\n"
        "TAS Tashkent\n"
        "SSH Sharm El Sheikh\n"
        "09:15 23.09.2026\n"
        "13:05 23.09.2026\n"
        "ECONOM\n"
        "30 kg\n"
        "23.09.2026"
    )


@dp.message(F.text)
async def handle_input(message: types.Message):
    try:
        data = parse_message(message.text)
        filename = BASE_DIR / f"confirm_{message.from_user.id}.pdf"
        build_pdf(data, filename)

        await message.answer_document(
            FSInputFile(filename, filename=f"{data['name']}.pdf"),
            caption=f"✅ {data['name']} uchun PDF tayyor!"
        )
    except Exception as exc:
        await message.answer(f"❌ Xatolik: {exc}")
    finally:
        try:
            if 'filename' in locals() and filename.exists():
                filename.unlink()
        except Exception:
            pass


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
