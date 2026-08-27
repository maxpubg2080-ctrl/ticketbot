import asyncio
import http.server
import os
import threading
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Render port talabini bajarishi uchun fonda ishlaydigan kichik veb-server
def run_server():
  port = int(os.environ.get('PORT', 10000))
  server_address = ('', port)
  httpd = http.server.HTTPServer(
      server_address, http.server.SimpleHTTPRequestHandler
  )
  httpd.serve_forever()


threading.Thread(target=run_server, daemon=True).start()

# Serverda muammo chiqmasligi uchun universal Helvetica shriftidan foydalanamiz
FONT_NAME = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

BOT_TOKEN = '8811288035:AAG5a0yOYEJI7jMwJJVloqE0jJU12W5oTLE'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ICON_DEP = 'https://cdn-icons-png.flaticon.com/512/3125/3125713.png'
ICON_BAG = 'https://cdn-icons-png.flaticon.com/512/2907/2907150.png'


def download_icon(url, filename):
  if not os.path.exists(filename):
    try:
      r = requests.get(url, timeout=5)
      if r.status_code == 200:
        with open(filename, 'wb') as f:
          f.write(r.content)
    except Exception:
      pass


def find_file(base_name):
  for ext in ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '']:
    path = f'{base_name}{ext}'
    if os.path.exists(path):
      return path
  return None


def get_airline_logo(airline_name):
  name = airline_name.lower().strip()

  if 'khiva' in name:
    path = find_file('flykhiva')
    if path:
      return Image(path, width=110, height=30)
  elif 'centrum' in name:
    path = find_file('centrum')
    if path:
      return Image(path, width=120, height=28)
  elif 'uzbekistan' in name or 'uzairways' in name or 'hy' in name:
    path = find_file('uzairways') or find_file('uzbekistan')
    if path:
      return Image(path, width=120, height=28)

  return Paragraph(
      f"<b>AIRLINE: {airline_name.upper()}</b>",
      ParagraphStyle('A', fontName=FONT_BOLD, fontSize=9, alignment=1),
  )


def format_title_gender(gender_str):
  g = gender_str.upper().strip()
  if g in ['MALE', 'M', 'ERKAK', 'MR']:
    return 'MR'
  elif g in ['FEMALE', 'F', 'AYOL', 'MRS', 'MS']:
    return 'MRS'
  return gender_str


def build_pdf_confirmation(data, filename):
  download_icon(ICON_DEP, 'icon_dep.png')
  download_icon(ICON_BAG, 'icon_bag.png')

  doc = SimpleDocTemplate(
      filename,
      pagesize=A4,
      rightMargin=20,
      leftMargin=20,
      topMargin=15,
      bottomMargin=15,
  )
  story = []

  PRIMARY_BLUE = colors.HexColor('#0F4C81')
  BG_CYAN = colors.HexColor('#EBF6FC')
  BORDER_CYAN = colors.HexColor('#93C5FD')

  styles = getSampleStyleSheet()

  style_title = ParagraphStyle(
      'T',
      parent=styles['Normal'],
      fontName=FONT_BOLD,
      fontSize=13,
      alignment=1,
      textColor=PRIMARY_BLUE,
      spaceAfter=8,
  )
  style_lbl_bold = ParagraphStyle(
      'LB',
      parent=styles['Normal'],
      fontName=FONT_BOLD,
      fontSize=8.5,
      textColor=PRIMARY_BLUE,
  )
  style_lbl = ParagraphStyle(
      'L', parent=styles['Normal'], fontName=FONT_NAME, fontSize=8, leading=10
  )
  style_c_bold = ParagraphStyle(
      'CB',
      parent=styles['Normal'],
      fontName=FONT_BOLD,
      fontSize=8.5,
      alignment=1,
      textColor=PRIMARY_BLUE,
  )
  style_c = ParagraphStyle(
      'C',
      parent=styles['Normal'],
      fontName=FONT_NAME,
      fontSize=8,
      alignment=1,
      leading=10,
  )
  style_disc = ParagraphStyle(
      'D',
      parent=styles['Normal'],
      fontName=FONT_NAME,
      fontSize=6.5,
      leading=8.5,
      textColor=colors.HexColor('#475569'),
  )

  story.append(Paragraph('CONFIRMATION / PODTVERZHDENIE', style_title))

  from_parts = data['from_city'].split()
  to_parts = data['to_city'].split()
  dep_code = (
      from_parts[0]
      if len(from_parts) > 1 and len(from_parts[0]) == 3
      else ''
  )
  dep_city_name = ' '.join(from_parts[1:]) if dep_code else data['from_city']
  arr_code = (
      to_parts[0] if len(to_parts) > 1 and len(to_parts[0]) == 3 else ''
  )
  arr_city_name = ' '.join(to_parts[1:]) if arr_code else data['to_city']
  route_title = f'{dep_city_name} - {arr_city_name}'.strip(' -')

  gt_logo = Paragraph('<b>GRAND TURAN</b>', style_lbl_bold)

  left_cell = [
      gt_logo,
      Spacer(1, 4),
      Paragraph('<b>Tour Dates:</b>', style_lbl_bold),
      Paragraph(f"{data['tour_dates']}", style_lbl),
      Spacer(1, 2),
      Paragraph('<b>Tour:</b>', style_lbl_bold),
      Paragraph(f'Aviabileyty {route_title}', style_lbl),
  ]

  right_cell = [
      Paragraph('<b>Client:</b>', style_lbl_bold),
      Paragraph('SHAMSIDDIN', style_lbl_bold),
      Paragraph('📞 +998 77 393 57 57', style_lbl),
      Paragraph(f'Aviabileyty {route_title}', style_lbl),
  ]

  top_table = Table([[left_cell, right_cell]], colWidths=[275, 280])
  top_table.setStyle(
      TableStyle([
          ('BACKGROUND', (0, 0), (-1, -1), BG_CYAN),
          ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('PADDING', (0, 0), (-1, -1), 6),
          ('BOX', (0, 0), (-1, -1), 0.5, BORDER_CYAN),
      ])
  )
  story.append(top_table)
  story.append(Spacer(1, 8))

  # Туристы
  t_hdr = Table(
      [[Paragraph('<u>TOURIST LIST:</u>', style_lbl_bold)]], colWidths=[555]
  )
  t_hdr.setStyle(
      TableStyle([
          ('BACKGROUND', (0, 0), (-1, -1), BG_CYAN),
          ('PADDING', (0, 0), (-1, -1), 3),
      ])
  )
  story.append(t_hdr)

  title_gender = format_title_gender(data['gender'])

  tourist_data = [
      [
          Paragraph('N', style_c_bold),
          Paragraph('Full Name', style_c_bold),
          Paragraph('Gender', style_c_bold),
          Paragraph('Passport', style_c_bold),
          Paragraph('Birth Date', style_c_bold),
      ],
      [
          Paragraph('1', style_c),
          Paragraph(f"<b>{data['name']}</b>", style_c),
          Paragraph(title_gender, style_c),
          Paragraph(data['passport'], style_c),
          Paragraph(data['birth_date'], style_c),
      ],
  ]
  t_table = Table(tourist_data, colWidths=[35, 210, 70, 120, 120])
  t_table.setStyle(
      TableStyle([
          ('GRID', (0, 0), (-1, -1), 0.5, BORDER_CYAN),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('PADDING', (0, 0), (-1, -1), 4),
      ])
  )
  story.append(t_table)
  story.append(Spacer(1, 8))

  # Транспорт
  tr_hdr = Table(
      [[Paragraph('<u>TRANSPORT:</u>', style_lbl_bold)]], colWidths=[555]
  )
  tr_hdr.setStyle(
      TableStyle([
          ('BACKGROUND', (0, 0), (-1, -1), BG_CYAN),
          ('PADDING', (0, 0), (-1, -1), 3),
      ])
  )
  story.append(tr_hdr)

  dep_img_path = find_file('icon_dep')
  bag_img_path = find_file('icon_bag')

  dep_img = (
      Image(dep_img_path, width=12, height=12)
      if dep_img_path
      else Paragraph('✈️', style_c)
  )
  bag_img = (
      Image(bag_img_path, width=12, height=12)
      if bag_img_path
      else Paragraph('🧳', style_c)
  )

  h_dep = Table(
      [[dep_img, Paragraph('<b>Departure</b>', style_c_bold)]],
      colWidths=[15, 110],
  )
  h_arr = Table(
      [[dep_img, Paragraph('<b>Arrival</b>', style_c_bold)]],
      colWidths=[15, 110],
  )
  h_bag = Table(
      [[bag_img, Paragraph('<b>Class/Baggage</b>', style_c_bold)]],
      colWidths=[15, 110],
  )

  airline_cell = [
      get_airline_logo(data['airline']),
      Spacer(1, 2),
      Paragraph(
          f"<font color='#475569'><b>{data['flight_code']}</b></font>", style_c
      ),
  ]

  dep_text = (
      f"<b>{dep_code}</b><br/>{dep_city_name}"
      if dep_code
      else f'<b>{dep_city_name}</b>'
  )
  dep_cell = [
      Paragraph(dep_text, style_c),
      Spacer(1, 2),
      Paragraph(f"time {data['dep_time']}", style_c),
  ]

  arr_text = (
      f"<b>{arr_code}</b><br/>{arr_city_name}"
      if arr_code
      else f'<b>{arr_city_name}</b>'
  )
  arr_cell = [
      Paragraph(arr_text, style_c),
      Spacer(1, 2),
      Paragraph(f"time {data['arr_time']}", style_c),
  ]

  bag_cell = [
      Paragraph('<b>ECONOM</b>', style_c_bold),
      Paragraph(f"Baggage up to {data['baggage']} kg", style_c),
  ]

  transport_data = [
      [Paragraph('<b>Airline</b>', style_c_bold), h_dep, h_arr, h_bag],
      [airline_cell, dep_cell, arr_cell, bag_cell],
  ]

  tr_table = Table(transport_data, colWidths=[145, 136, 137, 137])
  tr_table.setStyle(
      TableStyle([
          ('GRID', (0, 0), (-1, -1), 0.5, BORDER_CYAN),
          ('BACKGROUND', (0, 0), (-1, 0), BG_CYAN),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
          ('PADDING', (0, 0), (-1, -1), 4),
      ])
  )
  story.append(tr_table)
  story.append(Spacer(1, 10))

  disclaimers = [
      '* Upon receiving this confirmation, please check the accuracy of tourist details (Full Name, Date of Birth, Passport No., etc.) as they will be entered into all documents.',
      'The correctness of document completion is determined by this confirmation.',
      'The agency is responsible for the accuracy and precision of the specified information.',
      '* Cancellation of the selected tour must be made in written form. In the absence of a written cancellation, the application is considered valid and subject to full payment.',
      '* In case of tour cancellation, a penalty is charged according to the agency agreement.',
      '* Tour cancellation is made in full, including air travel.',
      '* Payment is made in UZS at the commercial exchange rate on the day of payment.',
      '* If the application cannot be fulfilled on site, the servicing party has the right to replace the program and conditions with equivalent ones.',
  ]
  for d_text in disclaimers:
    story.append(Paragraph(d_text, style_disc))
    story.append(Spacer(1, 1))

  doc.build(story)


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
  await message.answer("Salom! Ma'lumotlarni yuboring.")


@dp.message(F.text)
async def handle_input(message: types.Message):
  lines = [l.strip() for l in message.text.strip().split('\n') if l.strip()]
  if len(lines) < 11:
    await message.answer("⚠️ Ma'lumotlar kam! 11 yoki 12 qator yuboring.")
    return

  data = {
      'name': lines[0],
      'gender': lines[1],
      'passport': lines[2],
      'birth_date': lines[3],
      'airline': lines[4],
      'flight_code': lines[5],
      'from_city': lines[6],
      'to_city': lines[7],
      'dep_time': lines[8],
      'arr_time': lines[9],
      'baggage': lines[10].replace('Kg', '').replace('kg', '').strip(),
      'tour_dates': lines[11] if len(lines) > 11 else lines[8].split()[-1],
  }

  pdf_filename = f'confirm_{message.from_user.id}.pdf'
  try:
    build_pdf_confirmation(data, pdf_filename)
    doc_file = FSInputFile(pdf_filename, filename=f"{data['name']}.pdf")
    await message.answer_document(
        doc_file, caption=f"✅ {data['name']} uchun PDF tayyor!"
    )
  except Exception as e:
    await message.answer(f'❌ Xatolik: {str(e)}')
  finally:
    await asyncio.sleep(1)
    if os.path.exists(pdf_filename):
      try:
        os.remove(pdf_filename)
      except Exception:
        pass


async def main():
  await dp.start_polling(bot)


if __name__ == '__main__':
  asyncio.run(main())
