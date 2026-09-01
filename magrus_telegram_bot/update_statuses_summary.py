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

try:
    leads = spreadsheet.worksheet("Заявки")
except gspread.WorksheetNotFound:
    raise RuntimeError("Не найден лист 'Заявки'")

EXPECTED_HEADERS = [
    "ID заявки", "Дата заявки", "Имя", "Телефон", "Город", "Автомобиль",
    "Рассрочка", "План покупки", "Источник", "Статус", "Менеджер",
    "Взято в работу", "Комментарий", "Telegram", "Telegram ID",
]

headers = leads.row_values(1)[:len(EXPECTED_HEADERS)]
if headers != EXPECTED_HEADERS:
    raise RuntimeError(
        "Структура листа 'Заявки' отличается от ожидаемой. "
        "Скрипт остановлен, чтобы не повредить данные."
    )

STATUSES = [
    "Новый",
    "В работе",
    "Недозвон",
    "Сделали расчет - думает",
    "Заявка",
    "Договор",
    "Перезвон",
    "Отказ",
]

# Определяем локаль таблицы для правильного разделителя аргументов формул.
metadata = spreadsheet.fetch_sheet_metadata()
locale = (metadata.get("properties", {}).get("locale") or "").lower()
semicolon_locales = (
    "ru", "de", "fr", "it", "es", "pt", "pl", "uk", "tr", "nl",
    "cs", "sk", "fi", "sv", "da", "no"
)
sep = ";" if locale.startswith(semicolon_locales) else ","

print(f"Таблица: {spreadsheet.title}")
print(f"Локаль: {locale or 'не определена'}")
print("\nБудут внесены изменения:")
print("1. Новый выпадающий список статусов в колонке J.")
print("2. Новая сводка по всем статусам.")
print("3. Цветовое выделение новых статусов.")
print("4. Архивные листы Архив_Заявки_* будут удалены, если ещё остались.")
print("\nЛист 'Заявки' и данные клиентов удаляться не будут.")

answer = input("\nДля продолжения введите YES: ").strip()
if answer != "YES":
    print("Отменено. Изменения не внесены.")
    raise SystemExit(0)

# Подготовим запас строк, чтобы выпадающий список работал и для будущих заявок.
target_rows = max(leads.row_count, 5000)
if leads.row_count < target_rows or leads.col_count < 15:
    leads.resize(rows=target_rows, cols=max(leads.col_count, 15))

sheet_id = leads.id

def color(hex_value):
    h = hex_value.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue": int(h[4:6], 16) / 255,
    }

requests = [
    {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": target_rows,
                "startColumnIndex": 9,
                "endColumnIndex": 10,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": status} for status in STATUSES],
                },
                "strict": True,
                "showCustomUi": True,
            },
        }
    }
]

# Новые цветовые правила для статусов.
status_colors = {
    "Новый": "#FFF2CC",
    "В работе": "#D9EAF7",
    "Недозвон": "#FCE5CD",
    "Сделали расчет - думает": "#EADCF8",
    "Заявка": "#D9EAD3",
    "Договор": "#B6D7A8",
    "Перезвон": "#D0E0E3",
    "Отказ": "#F4CCCC",
}

for status, hex_color in status_colors.items():
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": target_rows,
                    "startColumnIndex": 9,
                    "endColumnIndex": 10,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": f'=$J2="{status}"'}],
                    },
                    "format": {
                        "backgroundColor": color(hex_color),
                        "textFormat": {"bold": True},
                    },
                },
            },
            "index": 0,
        }
    })

spreadsheet.batch_update({"requests": requests})

# Перестраиваем лист «Сводка».
try:
    summary = spreadsheet.worksheet("Сводка")
except gspread.WorksheetNotFound:
    summary = spreadsheet.add_worksheet(title="Сводка", rows=80, cols=8)

summary_values = [
    ["AKRAM AUTO — Сводка по заявкам", ""],
    ["", ""],
    ["Показатель", "Значение"],
    ["Всего заявок", f"=MAX(COUNTA('Заявки'!A:A)-1{sep}0)"],
    ["Новый", f'=COUNTIF(\'Заявки\'!J:J{sep}"Новый")'],
    ["В работе", f'=COUNTIF(\'Заявки\'!J:J{sep}"В работе")'],
    ["Недозвон", f'=COUNTIF(\'Заявки\'!J:J{sep}"Недозвон")'],
    ["Сделали расчет - думает", f'=COUNTIF(\'Заявки\'!J:J{sep}"Сделали расчет - думает")'],
    ["Заявка", f'=COUNTIF(\'Заявки\'!J:J{sep}"Заявка")'],
    ["Договор", f'=COUNTIF(\'Заявки\'!J:J{sep}"Договор")'],
    ["Перезвон", f'=COUNTIF(\'Заявки\'!J:J{sep}"Перезвон")'],
    ["Отказ", f'=COUNTIF(\'Заявки\'!J:J{sep}"Отказ")'],
    ["С рассрочкой", f'=COUNTIF(\'Заявки\'!G:G{sep}"Да")'],
    ["Без рассрочки", f'=COUNTIF(\'Заявки\'!G:G{sep}"Нет")'],
    ["Конверсия в договор", f"=IFERROR(B10/B4{sep}0)"],
]

summary.clear()
summary.resize(rows=80, cols=8)
summary.update(
    range_name="A1:B15",
    values=summary_values,
    value_input_option="USER_ENTERED",
)

summary.format("A1:B1", {
    "backgroundColor": color("#17324D"),
    "textFormat": {
        "bold": True,
        "foregroundColor": {"red": 1, "green": 1, "blue": 1},
        "fontSize": 14,
    },
    "horizontalAlignment": "CENTER",
})

summary.format("A3:B3", {
    "backgroundColor": color("#2F75B5"),
    "textFormat": {
        "bold": True,
        "foregroundColor": {"red": 1, "green": 1, "blue": 1},
    },
    "horizontalAlignment": "CENTER",
})

summary.format("A4:A15", {"textFormat": {"bold": True}})
summary.format("B15", {
    "numberFormat": {"type": "PERCENT", "pattern": "0.0%"}
})
summary.freeze(rows=1)

# Разумная ширина колонок.
summary.set_basic_filter("A3:B15")
summary.columns_auto_resize(0, 2)

# Удаляем архивные листы, если они ещё остались.
archive_sheets: List[str] = [
    ws.title for ws in spreadsheet.worksheets()
    if ws.title.startswith("Архив_Заявки_")
]
for title in archive_sheets:
    spreadsheet.del_worksheet(spreadsheet.worksheet(title))

print("\nГотово.")
print("Колонка J 'Статус' теперь имеет варианты:")
for status in STATUSES:
    print(f"- {status}")
print("Лист 'Сводка' перестроен под новую воронку.")
if archive_sheets:
    print("Архивные листы удалены.")
else:
    print("Архивных листов не было.")
print("Данные заявок не удалялись.")
