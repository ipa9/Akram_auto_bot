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
    ws = spreadsheet.worksheet("Заявки")
except gspread.WorksheetNotFound:
    raise RuntimeError("Не найден лист 'Заявки'")

NEW_HEADERS = [
    "ID заявки", "Дата заявки", "Имя", "Телефон", "Автомобиль",
    "Рассрочка", "Источник", "Статус", "Менеджер", "Взято в работу",
    "Комментарий", "Telegram", "Telegram ID",
]

CURRENT_15_HEADERS = [
    "ID заявки", "Дата заявки", "Имя", "Телефон", "Город", "Автомобиль",
    "Рассрочка", "План покупки", "Источник", "Статус", "Менеджер",
    "Взято в работу", "Комментарий", "Telegram", "Telegram ID",
]

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


def get(row, idx):
    return row[idx] if idx < len(row) else ""


def installment_value(raw):
    value = (raw or "").strip()
    if value.lower() == "да":
        return "Да"
    if value.lower() == "нет":
        return "Нет"
    if value.lower() == "не указано":
        return "Не указано"
    if value:
        return "Не указано"
    return ""


old_values = ws.get_all_values()
headers = old_values[0] if old_values else []
new_rows = []

if headers[:13] == NEW_HEADERS:
    # Таблица уже в новой структуре — сохраняем строки как есть.
    for row in old_values[1:]:
        padded = list(row[:13]) + [""] * max(0, 13 - len(row))
        if any(str(x).strip() for x in padded):
            new_rows.append(padded[:13])

elif headers[:15] == CURRENT_15_HEADERS:
    # Текущая структура v5: удаляем только Город (E) и План покупки (H).
    for row in old_values[1:]:
        if not any(str(x).strip() for x in row):
            continue
        new_rows.append([
            get(row, 0),   # A ID заявки
            get(row, 1),   # B Дата заявки
            get(row, 2),   # C Имя
            get(row, 3),   # D Телефон
            get(row, 5),   # E Автомобиль
            get(row, 6),   # F Рассрочка
            get(row, 8),   # G Источник
            get(row, 9) or "Новый",   # H Статус
            get(row, 10),  # I Менеджер
            get(row, 11),  # J Взято в работу
            get(row, 12),  # K Комментарий
            get(row, 13),  # L Telegram
            get(row, 14),  # M Telegram ID
        ])

else:
    # Поддержка самой старой структуры A:Q, если обновление v4/v5 не было завершено.
    # A ID, B Дата, C Telegram ID, D Username, E Имя, F Телефон,
    # G Город, H Автомобиль, I Бюджет/Рассрочка, J Взнос, K Срок,
    # L Поручители, M План покупки, N Источник, O Статус, P Менеджер, Q Комментарий.
    if len(headers) < 17:
        raise RuntimeError(
            "Не удалось распознать текущую структуру листа 'Заявки'. "
            "Скрипт остановлен, данные не изменены."
        )
    for row in old_values[1:]:
        if not any(str(x).strip() for x in row):
            continue
        new_rows.append([
            get(row, 0),                    # A ID заявки
            get(row, 1),                    # B Дата заявки
            get(row, 4),                    # C Имя
            get(row, 5),                    # D Телефон
            get(row, 7),                    # E Автомобиль
            installment_value(get(row, 8)), # F Рассрочка
            get(row, 13),                   # G Источник
            get(row, 14) or "Новый",       # H Статус
            get(row, 15),                   # I Менеджер
            "",                             # J Взято в работу
            get(row, 16),                   # K Комментарий
            get(row, 3),                    # L Telegram
            get(row, 2),                    # M Telegram ID
        ])

metadata = spreadsheet.fetch_sheet_metadata()
locale = (metadata.get("properties", {}).get("locale") or "").lower()
semicolon_locales = (
    "ru", "de", "fr", "it", "es", "pt", "pl", "uk", "tr", "nl",
    "cs", "sk", "fi", "sv", "da", "no"
)
sep = ";" if locale.startswith(semicolon_locales) else ","

print(f"Таблица: {spreadsheet.title}")
print(f"Лист: {ws.title}")
print(f"Локаль: {locale or 'не определена'}")
print("\nБудут внесены изменения:")
print("- удалены поля 'Город' и 'План покупки';")
print("- сохранены остальные данные заявок;")
print("- настроены статусы менеджеров;")
print("- перестроен лист 'Сводка';")
print("- архивные листы Архив_Заявки_* удалены, если они остались.")
print("\nОтдельный архивный лист создаваться НЕ будет.")

answer = input("\nДля продолжения введите YES: ").strip()
if answer != "YES":
    print("Отменено. Изменения не внесены.")
    raise SystemExit(0)

# Перезаписываем рабочий лист в структуру v6.
ws.clear()
rows_needed = max(5000, len(new_rows) + 100)
ws.resize(rows=rows_needed, cols=13)
ws.update(
    range_name=f"A1:M{len(new_rows) + 1}",
    values=[NEW_HEADERS] + new_rows,
    value_input_option="USER_ENTERED",
)

sheet_id = ws.id


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
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": 13,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": color("#17324D"),
                    "textFormat": {"bold": True, "foregroundColor": color("#FFFFFF")},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat",
        }
    },
    {
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": rows_needed,
                    "startColumnIndex": 0,
                    "endColumnIndex": 13,
                }
            }
        }
    },
    {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": rows_needed,
                "startColumnIndex": 5,
                "endColumnIndex": 6,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "Да"},
                        {"userEnteredValue": "Нет"},
                        {"userEnteredValue": "Не указано"},
                    ],
                },
                "strict": True,
                "showCustomUi": True,
            },
        }
    },
    {
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": rows_needed,
                "startColumnIndex": 7,
                "endColumnIndex": 8,
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
    },
]

widths = [105, 140, 150, 135, 200, 110, 120, 190, 155, 150, 250, 155, 130]
for idx, px in enumerate(widths):
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": idx,
                "endIndex": idx + 1,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    })

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
                    "endRowIndex": rows_needed,
                    "startColumnIndex": 7,
                    "endColumnIndex": 8,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": f'=$H2="{status}"'}],
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

# Сводка.
try:
    summary = spreadsheet.worksheet("Сводка")
except gspread.WorksheetNotFound:
    summary = spreadsheet.add_worksheet(title="Сводка", rows=80, cols=8)

summary_values = [
    ["AKRAM AUTO — Сводка по заявкам", ""],
    ["", ""],
    ["Показатель", "Значение"],
    ["Всего заявок", f"=MAX(COUNTA('Заявки'!A:A)-1{sep}0)"],
    ["Новый", f'=COUNTIF(\'Заявки\'!H:H{sep}"Новый")'],
    ["В работе", f'=COUNTIF(\'Заявки\'!H:H{sep}"В работе")'],
    ["Недозвон", f'=COUNTIF(\'Заявки\'!H:H{sep}"Недозвон")'],
    ["Сделали расчет - думает", f'=COUNTIF(\'Заявки\'!H:H{sep}"Сделали расчет - думает")'],
    ["Заявка", f'=COUNTIF(\'Заявки\'!H:H{sep}"Заявка")'],
    ["Договор", f'=COUNTIF(\'Заявки\'!H:H{sep}"Договор")'],
    ["Перезвон", f'=COUNTIF(\'Заявки\'!H:H{sep}"Перезвон")'],
    ["Отказ", f'=COUNTIF(\'Заявки\'!H:H{sep}"Отказ")'],
    ["С рассрочкой", f'=COUNTIF(\'Заявки\'!F:F{sep}"Да")'],
    ["Без рассрочки", f'=COUNTIF(\'Заявки\'!F:F{sep}"Нет")'],
    ["Конверсия в договор", f"=IFERROR(B10/B4{sep}0)"],
]

summary.clear()
summary.resize(rows=80, cols=8)
summary.update(range_name="A1:B15", values=summary_values, value_input_option="USER_ENTERED")
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
summary.format("A4:A15", {"textFormat": {"bold": True}})
summary.format("B15", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
summary.freeze(rows=1)

# Удаляем архивы, если они остались. Новых архивов не создаём.
archive_sheets: List[str] = [
    sheet.title for sheet in spreadsheet.worksheets()
    if sheet.title.startswith("Архив_Заявки_")
]
for title in archive_sheets:
    spreadsheet.del_worksheet(spreadsheet.worksheet(title))

print("\nГотово.")
print("Лист 'Заявки' переведен на структуру v6 (13 колонок).")
print("Поля 'Город' и 'План покупки' удалены.")
print("Статусы и 'Сводка' обновлены.")
if archive_sheets:
    print("Архивные листы удалены.")
print("Теперь замените bot.py на bot_updated_v6.py и запустите бота.")
