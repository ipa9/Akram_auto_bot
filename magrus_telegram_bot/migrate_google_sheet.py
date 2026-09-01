import os
from datetime import datetime
from zoneinfo import ZoneInfo

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
ws = spreadsheet.worksheet("Заявки")

NEW_HEADERS = [
    "ID заявки", "Дата заявки", "Имя", "Телефон", "Город", "Автомобиль",
    "Рассрочка", "План покупки", "Источник", "Статус", "Менеджер",
    "Взято в работу", "Комментарий", "Telegram", "Telegram ID",
]

print(f"Таблица: {spreadsheet.title}")
print(f"Лист: {ws.title}")
print("\nСкрипт сделает резервную копию листа и приведет таблицу к новой структуре.")
answer = input("Для продолжения введите YES: ").strip()
if answer != "YES":
    print("Отменено. Никаких изменений не внесено.")
    raise SystemExit(0)

# 1) Резервная копия листа
stamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y%m%d_%H%M%S")
archive_name = f"Архив_Заявки_{stamp}"
ws.duplicate(new_sheet_name=archive_name)
print(f"Создан архив: {archive_name}")

# 2) Читаем текущие данные
old_values = ws.get_all_values()
current_headers = old_values[0][:15] if old_values else []


def get(row, idx):
    return row[idx] if idx < len(row) else ""


def installment_value(raw):
    value = (raw or "").strip()
    if value.lower() == "да":
        return "Да"
    if value.lower() == "нет":
        return "Нет"
    if value:
        # Раньше в этой колонке мог храниться бюджет. Не выдаем его за ответ по рассрочке.
        return "Не указано"
    return ""

new_rows = []

if current_headers == NEW_HEADERS:
    # Повторный запуск: структура уже новая, просто сохраняем данные.
    for row in old_values[1:]:
        padded = list(row[:15]) + [""] * max(0, 15 - len(row))
        if any(str(x).strip() for x in padded):
            new_rows.append(padded[:15])
else:
    # Старая структура A:Q:
    # A ID, B Дата, C Telegram ID, D Username, E Имя, F Телефон,
    # G Город, H Автомобиль, I Бюджет/Рассрочка, J Первый взнос,
    # K Срок, L Поручители, M План покупки, N Источник,
    # O Статус, P Менеджер, Q Комментарий.
    for row in old_values[1:]:
        if not any(str(x).strip() for x in row):
            continue
        new_rows.append([
            get(row, 0),                    # A ID заявки
            get(row, 1),                    # B Дата заявки
            get(row, 4),                    # C Имя
            get(row, 5),                    # D Телефон
            get(row, 6),                    # E Город
            get(row, 7),                    # F Автомобиль
            installment_value(get(row, 8)), # G Рассрочка
            get(row, 12),                   # H План покупки
            get(row, 13),                   # I Источник
            get(row, 14) or "Новый",        # J Статус
            get(row, 15),                   # K Менеджер
            "",                             # L Взято в работу (раньше не фиксировалось)
            get(row, 16),                   # M Комментарий
            get(row, 3),                    # N Telegram
            get(row, 2),                    # O Telegram ID
        ])

# 3) Перезаписываем лист в новой структуре
ws.clear()
rows_needed = max(1000, len(new_rows) + 100)
ws.resize(rows=rows_needed, cols=15)
ws.update(range_name=f"A1:O{len(new_rows)+1}", values=[NEW_HEADERS] + new_rows, value_input_option="USER_ENTERED")

# 4) Оформление листа через Google Sheets API
sheet_id = ws.id
last_row = rows_needed

def color(hex_value):
    h = hex_value.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue": int(h[4:6], 16) / 255,
    }

requests = [
    {
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    },
    {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 15},
            "cell": {"userEnteredFormat": {
                "backgroundColor": color("#17324D"),
                "textFormat": {"bold": True, "foregroundColor": color("#FFFFFF")},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            }},
            "fields": "userEnteredFormat",
        }
    },
    {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 36},
            "fields": "pixelSize",
        }
    },
    {
        "setBasicFilter": {
            "filter": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": 15}}
        }
    },
    {
        "setDataValidation": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": last_row, "startColumnIndex": 6, "endColumnIndex": 7},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Да"}, {"userEnteredValue": "Нет"}, {"userEnteredValue": "Не указано"}]},
                "strict": False,
                "showCustomUi": True,
            },
        }
    },
    {
        "setDataValidation": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": last_row, "startColumnIndex": 9, "endColumnIndex": 10},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [
                    {"userEnteredValue": "Новый"},
                    {"userEnteredValue": "В работе"},
                    {"userEnteredValue": "Связались"},
                    {"userEnteredValue": "Думает"},
                    {"userEnteredValue": "Одобрено"},
                    {"userEnteredValue": "Сделка"},
                    {"userEnteredValue": "Отказ"},
                ]},
                "strict": False,
                "showCustomUi": True,
            },
        }
    },
]

# Ширины колонок в пикселях
widths = [105, 140, 150, 130, 135, 190, 105, 165, 120, 125, 150, 145, 240, 150, 125]
for idx, px in enumerate(widths):
    requests.append({
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": idx, "endIndex": idx + 1},
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    })

# Полосатая таблица
requests.append({
    "addBanding": {
        "bandedRange": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": 15},
            "rowProperties": {
                "headerColor": color("#17324D"),
                "firstBandColor": color("#F8FBFD"),
                "secondBandColor": color("#EAF3F8"),
            },
        }
    }
})

# Цвет статусов
status_colors = {
    "Новый": "#FFF2CC",
    "В работе": "#D9EAF7",
    "Сделка": "#D9EAD3",
    "Отказ": "#F4CCCC",
}
for status, hex_color in status_colors.items():
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": last_row, "startColumnIndex": 9, "endColumnIndex": 10}],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=$J2="{status}"'}]},
                    "format": {"backgroundColor": color(hex_color), "textFormat": {"bold": True}},
                },
            },
            "index": 0,
        }
    })

spreadsheet.batch_update({"requests": requests})

# 5) Сводка
try:
    summary = spreadsheet.worksheet("Сводка")
    summary.clear()
except gspread.WorksheetNotFound:
    summary = spreadsheet.add_worksheet(title="Сводка", rows=60, cols=8)

summary_values = [
    ["AKRAM AUTO — Сводка по заявкам", ""],
    ["", ""],
    ["Показатель", "Значение"],
    ["Всего заявок", "=MAX(COUNTA('Заявки'!A:A)-1,0)"],
    ["Новые", '=COUNTIF(\'Заявки\'!J:J,"Новый")'],
    ["В работе", '=COUNTIF(\'Заявки\'!J:J,"В работе")'],
    ["С рассрочкой", '=COUNTIF(\'Заявки\'!G:G,"Да")'],
    ["Без рассрочки", '=COUNTIF(\'Заявки\'!G:G,"Нет")'],
    ["Сделки", '=COUNTIF(\'Заявки\'!J:J,"Сделка")'],
    ["Конверсия в сделку", '=IFERROR(B9/B4,0)'],
]
summary.update(range_name="A1:B10", values=summary_values, value_input_option="USER_ENTERED")
summary.format("A1:B1", {
    "backgroundColor": color("#17324D"),
    "textFormat": {"bold": True, "foregroundColor": color("#FFFFFF"), "fontSize": 14},
    "horizontalAlignment": "CENTER",
})
summary.format("A3:B3", {
    "backgroundColor": color("#2F75B5"),
    "textFormat": {"bold": True, "foregroundColor": color("#FFFFFF")},
    "horizontalAlignment": "CENTER",
})
summary.format("A4:A10", {"textFormat": {"bold": True}})
summary.format("B10", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
summary.freeze(rows=1)
summary.resize(rows=60, cols=8)

print("\nГотово.")
print(f"Новая структура применена к листу 'Заявки'.")
print(f"Старая версия сохранена в листе '{archive_name}'.")
print("Создан/обновлен лист 'Сводка'.")
print("Теперь замените bot.py на bot_updated_v4.py и запустите бота.")
