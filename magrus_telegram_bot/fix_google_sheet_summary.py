import os
from typing import List

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID", "").strip()
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS", "service_account.json").strip()

if not SHEET_ID:
    raise RuntimeError("SHEET_ID не указан в .env")
if not os.path.exists(GOOGLE_CREDS):
    raise RuntimeError(f"Не найден файл Google-ключа: {GOOGLE_CREDS}")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_file(GOOGLE_CREDS, scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SHEET_ID)

# Определяем локаль таблицы, чтобы использовать правильный разделитель аргументов в формулах.
metadata = spreadsheet.fetch_sheet_metadata()
locale = (metadata.get("properties", {}).get("locale") or "").lower()
semicolon_locales = (
    "ru", "de", "fr", "it", "es", "pt", "pl", "uk", "tr", "nl", "cs", "sk", "fi", "sv", "da", "no"
)
sep = ";" if locale.startswith(semicolon_locales) else ","

print(f"Таблица: {spreadsheet.title}")
print(f"Локаль: {locale or 'не определена'}")
print(f"Разделитель формул: {sep}")

# 1. Исправляем лист «Сводка».
try:
    summary = spreadsheet.worksheet("Сводка")
except gspread.WorksheetNotFound:
    summary = spreadsheet.add_worksheet(title="Сводка", rows=60, cols=8)

summary_values = [
    ["AKRAM AUTO — Сводка по заявкам", ""],
    ["", ""],
    ["Показатель", "Значение"],
    ["Всего заявок", f"=MAX(COUNTA('Заявки'!A:A)-1{sep}0)"],
    ["Новые", f'=COUNTIF(\'Заявки\'!J:J{sep}"Новый")'],
    ["В работе", f'=COUNTIF(\'Заявки\'!J:J{sep}"В работе")'],
    ["С рассрочкой", f'=COUNTIF(\'Заявки\'!G:G{sep}"Да")'],
    ["Без рассрочки", f'=COUNTIF(\'Заявки\'!G:G{sep}"Нет")'],
    ["Сделки", f'=COUNTIF(\'Заявки\'!J:J{sep}"Сделка")'],
    ["Конверсия в сделку", f"=IFERROR(B9/B4{sep}0)"],
]

summary.clear()
summary.resize(rows=60, cols=8)
summary.update(range_name="A1:B10", values=summary_values, value_input_option="USER_ENTERED")

# Оформление сводки.
summary.format("A1:B1", {
    "backgroundColor": {"red": 23/255, "green": 50/255, "blue": 77/255},
    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}, "fontSize": 14},
    "horizontalAlignment": "CENTER",
})
summary.format("A3:B3", {
    "backgroundColor": {"red": 47/255, "green": 117/255, "blue": 181/255},
    "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
    "horizontalAlignment": "CENTER",
})
summary.format("A4:A10", {"textFormat": {"bold": True}})
summary.format("B10", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
summary.freeze(rows=1)

# 2. Удаляем архивные листы — они не используются ботом.
archive_sheets: List[str] = [
    ws.title for ws in spreadsheet.worksheets() if ws.title.startswith("Архив_Заявки_")
]

for title in archive_sheets:
    ws = spreadsheet.worksheet(title)
    spreadsheet.del_worksheet(ws)

print("\nГотово.")
print("Лист 'Сводка' исправлен.")
if archive_sheets:
    print("Удалены архивные листы:")
    for title in archive_sheets:
        print(f"- {title}")
else:
    print("Архивных листов не найдено.")
print("Лист 'Заявки' и данные клиентов не изменялись.")
