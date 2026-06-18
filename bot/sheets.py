"""
Google Sheets bilan ishlash moduli.

Telegram bot to'plagan shartnoma ma'lumotlarini Google Sheets jadvaliga
qator (row) sifatida qo'shadi.

Kerakli sozlamalar (.env yoki muhit o'zgaruvchilari orqali):
    GOOGLE_SHEET_ID          - Google Sheets jadvalining ID si
    GOOGLE_CREDENTIALS_FILE  - service account JSON fayli yo'li
                               (standart: credentials.json)
    GOOGLE_WORKSHEET_NAME    - varaq (list) nomi (standart: birinchi varaq)
"""

import os

import gspread
from google.oauth2.service_account import Credentials

# Google Sheets bilan ishlash uchun zarur ruxsat doirasi
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
WORKSHEET_NAME = os.environ.get("GOOGLE_WORKSHEET_NAME", "")

# Jadvaldagi ustunlar tartibi (bot.py dagi FIELDS bilan mos bo'lishi kerak)
HEADERS = [
    "Qo'shilgan vaqt",
    "Bemor ismi",
    "Bemor familiyasi",
    "Otasining ismi",
    "Tug'ilgan sana",
    "Telefon",
    "Manzil",
    "Tashxis",
    "Implant / mahsulot",
    "Shifokor",
    "Operatsiya sanasi",
    "Summa",
    "Izoh",
    "Operator (Telegram)",
]

# Bir marta ulanib, qayta-qayta foydalanish uchun keshlangan varaq
_worksheet = None


def _connect():
    """Google Sheets'ga ulanib, ishchi varaqni qaytaradi."""
    if not SHEET_ID:
        raise RuntimeError(
            "GOOGLE_SHEET_ID o'rnatilmagan. .env faylga jadval ID sini yozing."
        )
    if not os.path.exists(CREDENTIALS_FILE):
        raise RuntimeError(
            f"Service account fayli topilmadi: {CREDENTIALS_FILE}. "
            "README.md dagi ko'rsatmaga qarang."
        )

    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)

    if WORKSHEET_NAME:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    else:
        worksheet = spreadsheet.sheet1

    # Birinchi qator bo'sh bo'lsa - ustun sarlavhalarini yozib qo'yamiz
    first_row = worksheet.row_values(1)
    if not first_row:
        worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")

    return worksheet


def get_worksheet():
    """Keshlangan varaqni qaytaradi, kerak bo'lsa ulanadi."""
    global _worksheet
    if _worksheet is None:
        _worksheet = _connect()
    return _worksheet


def append_contract(values):
    """Shartnoma ma'lumotlarini jadvalga yangi qator sifatida qo'shadi.

    values - HEADERS tartibiga mos ro'yxat (list).
    """
    worksheet = get_worksheet()
    worksheet.append_row(values, value_input_option="USER_ENTERED")


def check_connection():
    """Ulanishni tekshiradi. Muvaffaqiyatli bo'lsa jadval nomini qaytaradi."""
    worksheet = get_worksheet()
    return worksheet.spreadsheet.title
