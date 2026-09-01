import asyncio
import html
import os
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SHEET_ID = os.getenv("SHEET_ID", "").strip()
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS", "service_account.json").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не указан в файле .env")
if not SHEET_ID:
    raise RuntimeError("SHEET_ID не указан в файле .env")
if not os.path.exists(GOOGLE_CREDS):
    raise RuntimeError(f"Не найден файл Google-ключа: {GOOGLE_CREDS}")


# ============================================================
# GOOGLE SHEETS
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

credentials = Credentials.from_service_account_file(
    GOOGLE_CREDS,
    scopes=SCOPES,
)

gc = gspread.authorize(credentials)
spreadsheet = gc.open_by_key(SHEET_ID)
leads_sheet = spreadsheet.worksheet("Заявки")


def save_lead(row: list) -> None:
    leads_sheet.append_row(row, value_input_option="USER_ENTERED")


def take_lead_in_sheet(lead_id: str, manager: str) -> tuple[bool, str]:
    """Возвращает (успех, текущий_менеджер_или_сообщение)."""
    cell = leads_sheet.find(lead_id, in_column=1)
    if not cell:
        return False, "Заявка не найдена"

    status = (leads_sheet.cell(cell.row, 15).value or "").strip()
    current_manager = (leads_sheet.cell(cell.row, 16).value or "").strip()

    if status != "Новый":
        return False, current_manager or status or "Уже взята в работу"

    leads_sheet.update_cell(cell.row, 15, "В работе")
    leads_sheet.update_cell(cell.row, 16, manager)
    return True, manager


# ============================================================
# BOT
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()
router = Router()
dp.include_router(router)


# ============================================================
# STATES
# ============================================================

class Application(StatesGroup):
    car = State()
    custom_car = State()
    budget = State()
    custom_budget = State()
    payment = State()
    custom_payment = State()
    term = State()
    custom_term = State()
    guarantors = State()
    city = State()
    purchase_time = State()
    name = State()
    phone = State()
    confirm = State()


# ============================================================
# DATA / LABELS
# ============================================================

CAR_NAMES = {
    "uniz": "Changan UNI-Z",
    "cs75": "Changan CS75 Plus",
    "cs55": "Changan CS55 Plus",
    "aion05": "Aion 05",
    "unknown": "Пока не определился",
}

BUDGETS = {
    "b1": "До 1 500 000 ₽",
    "b2": "1 500 000–2 000 000 ₽",
    "b3": "2 000 000–3 000 000 ₽",
    "b4": "3 000 000–5 000 000 ₽",
    "b5": "5 000 000–10 000 000 ₽",
}

PAYMENTS = {
    "p25": "25%",
    "p30": "30%",
    "p40": "40%",
    "p50": "50%",
    "p60": "60%",
    "p70": "70%",
    "p80": "80%",
}

TERMS = {
    "t6": "6 месяцев",
    "t12": "12 месяцев",
    "t18": "18 месяцев",
    "t24": "24 месяца",
}

GUARANTORS = {
    "yes": "Да",
    "no": "Нет",
    "ask": "Нужно уточнить",
}

PURCHASE_TIMES = {
    "now": "Как можно скорее",
    "month": "В течение месяца",
    "1_3": "1–3 месяца",
    "look": "Пока изучаю варианты",
}


# ============================================================
# KEYBOARDS
# ============================================================

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚘 Подобрать автомобиль", callback_data="apply")],
            [InlineKeyboardButton(text="💳 Условия рассрочки", callback_data="terms")],
            [InlineKeyboardButton(text="👤 Оставить заявку", callback_data="apply")],
            [InlineKeyboardButton(text="☎️ Акрам Авто", callback_data="contact")],
        ]
    )


def info_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Оставить заявку", callback_data="apply")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")],
        ]
    )


def car_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Changan UNI-Z", callback_data="car:uniz")],
            [InlineKeyboardButton(text="Changan CS75 Plus", callback_data="car:cs75")],
            [InlineKeyboardButton(text="Changan CS55 Plus", callback_data="car:cs55")],
            [InlineKeyboardButton(text="Aion 05", callback_data="car:aion05")],
            [InlineKeyboardButton(text="🚘 Другая модель", callback_data="car:other")],
            [InlineKeyboardButton(text="🤷 Пока не определился", callback_data="car:unknown")],
        ]
    )


def budget_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="До 1 500 000 ₽", callback_data="budget:b1")],
            [InlineKeyboardButton(text="1,5–2 млн ₽", callback_data="budget:b2")],
            [InlineKeyboardButton(text="2–3 млн ₽", callback_data="budget:b3")],
            [InlineKeyboardButton(text="3–5 млн ₽", callback_data="budget:b4")],
            [InlineKeyboardButton(text="5–10 млн ₽", callback_data="budget:b5")],
            [InlineKeyboardButton(text="✍️ Указать самостоятельно", callback_data="budget:custom")],
        ]
    )


def payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="25%", callback_data="payment:p25"),
                InlineKeyboardButton(text="30%", callback_data="payment:p30"),
            ],
            [
                InlineKeyboardButton(text="40%", callback_data="payment:p40"),
                InlineKeyboardButton(text="50%", callback_data="payment:p50"),
            ],
            [
                InlineKeyboardButton(text="60%", callback_data="payment:p60"),
                InlineKeyboardButton(text="70%", callback_data="payment:p70"),
            ],
            [InlineKeyboardButton(text="80%", callback_data="payment:p80")],
            [InlineKeyboardButton(text="💰 Указать сумму", callback_data="payment:custom")],
        ]
    )


def term_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="6 месяцев", callback_data="term:t6"),
                InlineKeyboardButton(text="12 месяцев", callback_data="term:t12"),
            ],
            [
                InlineKeyboardButton(text="18 месяцев", callback_data="term:t18"),
                InlineKeyboardButton(text="24 месяца", callback_data="term:t24"),
            ],
            [InlineKeyboardButton(text="Другой срок", callback_data="term:custom")],
        ]
    )


def guarantors_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="guarantors:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="guarantors:no"),
            ],
            [InlineKeyboardButton(text="❓ Нужно уточнить", callback_data="guarantors:ask")],
        ]
    )


def purchase_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Как можно скорее", callback_data="time:now")],
            [InlineKeyboardButton(text="В течение месяца", callback_data="time:month")],
            [InlineKeyboardButton(text="1–3 месяца", callback_data="time:1_3")],
            [InlineKeyboardButton(text="Пока изучаю варианты", callback_data="time:look")],
        ]
    )


# ============================================================
# HELPERS
# ============================================================

async def ask_budget(message: Message, state: FSMContext) -> None:
    await state.set_state(Application.budget)
    await message.answer(
        "<b>💰 Какой бюджет автомобиля рассматриваете?</b>",
        reply_markup=budget_keyboard(),
    )


async def ask_payment(message: Message, state: FSMContext) -> None:
    await state.set_state(Application.payment)
    await message.answer(
        "<b>💳 Какой первоначальный взнос планируете?</b>\n\n"
        "По условиям рассрочки первоначальный взнос — от <b>25% до 80%</b>.",
        reply_markup=payment_keyboard(),
    )


async def ask_term(message: Message, state: FSMContext) -> None:
    await state.set_state(Application.term)
    await message.answer(
        "<b>📅 Какой срок рассрочки рассматриваете?</b>\n\n"
        "Доступный срок — от <b>2 до 24 месяцев</b>.",
        reply_markup=term_keyboard(),
    )


async def ask_guarantors(message: Message, state: FSMContext) -> None:
    await state.set_state(Application.guarantors)
    await message.answer(
        "<b>👥 Есть ли возможность предоставить двух поручителей?</b>",
        reply_markup=guarantors_keyboard(),
    )


async def show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(Application.confirm)

    text = (
        "<b>📋 Проверьте заявку</b>\n\n"
        f"🚘 Автомобиль: <b>{html.escape(data['car'])}</b>\n"
        f"💰 Бюджет: <b>{html.escape(data['budget'])}</b>\n"
        f"💳 Первый взнос: <b>{html.escape(data['payment'])}</b>\n"
        f"📅 Срок: <b>{html.escape(data['term'])}</b>\n"
        f"👥 2 поручителя: <b>{html.escape(data['guarantors'])}</b>\n"
        f"📍 Город: <b>{html.escape(data['city'])}</b>\n"
        f"⏱ Покупка: <b>{html.escape(data['purchase_time'])}</b>\n"
        f"👤 Имя: <b>{html.escape(data['name'])}</b>\n"
        f"📱 Телефон: <b>{html.escape(data['phone'])}</b>\n\n"
        "Всё верно?"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="submit")],
            [InlineKeyboardButton(text="🔄 Заполнить заново", callback_data="apply")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_application")],
        ]
    )

    await message.answer(text, reply_markup=keyboard)


def normalize_phone(raw: str) -> str | None:
    raw = raw.strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10 or len(digits) > 15:
        return None
    if raw.startswith("+"):
        return "+" + digits
    return digits


# ============================================================
# COMMANDS / START
# ============================================================

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    source = parts[1].strip() if len(parts) > 1 else "direct"

    await state.clear()
    await state.update_data(source=source)

    await message.answer(
        "<b>Здравствуйте! 👋</b>\n\n"
        "Здесь вы можете ознакомиться с условиями приобретения автомобиля "
        "и оставить заявку.\n\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    old = await state.get_data()
    source = old.get("source", "direct")
    await state.clear()
    await state.update_data(source=source)
    await message.answer(
        "Заполнение заявки отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Главное меню:", reply_markup=main_menu())


@router.message(Command("chatid"))
async def chat_id(message: Message) -> None:
    await message.answer(f"ID этого чата:\n<code>{message.chat.id}</code>")


# ============================================================
# INFO SECTIONS
# ============================================================

@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery) -> None:
    await callback.message.answer("Выберите нужный раздел:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "terms")
async def terms(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "<b>💳 Условия рассрочки «МАГ-РУС»</b>\n\n"
        "📅 Срок рассрочки: <b>от 2 до 24 месяцев</b>\n"
        "💰 Сумма: <b>от 500 000 ₽ до 10 000 000 ₽</b>\n"
        "👥 Необходимо: <b>2 поручителя</b>\n"
        "💳 Первый взнос: <b>от 25% до 80%</b>",
        reply_markup=info_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "contact")
async def contact(callback: CallbackQuery) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Позвонить", url="tel:+79880380606")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")],
        ]
    )
    await callback.message.answer(
        "<b>☎️ Акрам Авто</b>\n\n"
        "Телефон: <b>8 988 038-06-06</b>",
        reply_markup=keyboard,
    )
    await callback.answer()


# ============================================================
# APPLICATION FLOW
# ============================================================

@router.callback_query(F.data == "apply")
async def application_start(callback: CallbackQuery, state: FSMContext) -> None:
    old = await state.get_data()
    source = old.get("source", "direct")
    await state.clear()
    await state.update_data(source=source)
    await state.set_state(Application.car)
    await callback.message.answer(
        "<b>🚘 Какой автомобиль вас интересует?</b>",
        reply_markup=car_keyboard(),
    )
    await callback.answer()


@router.callback_query(Application.car, F.data.startswith("car:"))
async def select_car(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    if code == "other":
        await state.set_state(Application.custom_car)
        await callback.message.answer("Напишите марку и модель автомобиля:")
        await callback.answer()
        return

    await state.update_data(car=CAR_NAMES[code])
    await ask_budget(callback.message, state)
    await callback.answer()


@router.message(Application.custom_car)
async def custom_car(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Напишите марку и модель автомобиля текстом.")
        return
    await state.update_data(car=text)
    await ask_budget(message, state)


@router.callback_query(Application.budget, F.data.startswith("budget:"))
async def budget(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    if code == "custom":
        await state.set_state(Application.custom_budget)
        await callback.message.answer("Введите ориентировочный бюджет, например: <b>2 300 000 ₽</b>")
        await callback.answer()
        return

    await state.update_data(budget=BUDGETS[code])
    await ask_payment(callback.message, state)
    await callback.answer()


@router.message(Application.custom_budget)
async def custom_budget(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите ориентировочный бюджет.")
        return
    await state.update_data(budget=text)
    await ask_payment(message, state)


@router.callback_query(Application.payment, F.data.startswith("payment:"))
async def payment(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    if code == "custom":
        await state.set_state(Application.custom_payment)
        await callback.message.answer(
            "Введите сумму первоначального взноса, например: <b>700 000 ₽</b>"
        )
        await callback.answer()
        return

    await state.update_data(payment=PAYMENTS[code])
    await ask_term(callback.message, state)
    await callback.answer()


@router.message(Application.custom_payment)
async def custom_payment(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите сумму первоначального взноса.")
        return
    await state.update_data(payment=text)
    await ask_term(message, state)


@router.callback_query(Application.term, F.data.startswith("term:"))
async def term(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    if code == "custom":
        await state.set_state(Application.custom_term)
        await callback.message.answer("Введите количество месяцев от <b>2 до 24</b>:")
        await callback.answer()
        return

    await state.update_data(term=TERMS[code])
    await ask_guarantors(callback.message, state)
    await callback.answer()


@router.message(Application.custom_term)
async def custom_term(message: Message, state: FSMContext) -> None:
    try:
        months = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите только число от 2 до 24.")
        return

    if not 2 <= months <= 24:
        await message.answer("Срок должен быть от 2 до 24 месяцев.")
        return

    await state.update_data(term=f"{months} месяцев")
    await ask_guarantors(message, state)


@router.callback_query(Application.guarantors, F.data.startswith("guarantors:"))
async def guarantors(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await state.update_data(guarantors=GUARANTORS[code])
    await state.set_state(Application.city)
    await callback.message.answer("<b>📍 Из какого вы города/населённого пункта?</b>")
    await callback.answer()


@router.message(Application.city)
async def city(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Напишите город или населённый пункт.")
        return
    await state.update_data(city=text)
    await state.set_state(Application.purchase_time)
    await message.answer(
        "<b>⏱ Когда планируете приобрести автомобиль?</b>",
        reply_markup=purchase_time_keyboard(),
    )


@router.callback_query(Application.purchase_time, F.data.startswith("time:"))
async def purchase_time(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    await state.update_data(purchase_time=PURCHASE_TIMES[code])
    await state.set_state(Application.name)
    await callback.message.answer("<b>👤 Как к вам обращаться?</b>")
    await callback.answer()


@router.message(Application.name)
async def name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Напишите имя текстом.")
        return

    await state.update_data(name=text)
    await state.set_state(Application.phone)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await message.answer(
        "<b>📱 Оставьте номер телефона для связи.</b>\n\n"
        "Нажмите кнопку «Отправить мой номер» или отправьте номер сообщением.",
        reply_markup=keyboard,
    )


@router.message(Application.phone)
async def phone(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() == "❌ Отмена":
        old = await state.get_data()
        source = old.get("source", "direct")
        await state.clear()
        await state.update_data(source=source)
        await message.answer("Заполнение заявки отменено.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Главное меню:", reply_markup=main_menu())
        return

    if message.contact:
        if message.contact.user_id and message.contact.user_id != message.from_user.id:
            await message.answer("Пожалуйста, отправьте свой номер или введите его вручную.")
            return
        phone_number = message.contact.phone_number
    else:
        phone_number = normalize_phone(message.text or "")
        if not phone_number:
            await message.answer(
                "Не получилось распознать номер. Отправьте номер в формате +7XXXXXXXXXX "
                "или нажмите кнопку «Отправить мой номер»."
            )
            return

    await state.update_data(phone=phone_number)
    await message.answer("Спасибо.", reply_markup=ReplyKeyboardRemove())
    await show_confirmation(message, state)


@router.callback_query(F.data == "cancel_application")
async def cancel_application(callback: CallbackQuery, state: FSMContext) -> None:
    old = await state.get_data()
    source = old.get("source", "direct")
    await state.clear()
    await state.update_data(source=source)
    await callback.message.answer("Заявка отменена.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(Application.confirm, F.data == "submit")
async def submit(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()

    lead_id = uuid.uuid4().hex[:8].upper()
    now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
    username = f"@{callback.from_user.username}" if callback.from_user.username else ""

    row = [
        lead_id,                       # A ID
        now,                           # B Дата
        callback.from_user.id,         # C Telegram ID
        username,                      # D Username
        data["name"],                  # E Имя
        data["phone"],                 # F Телефон
        data["city"],                  # G Город
        data["car"],                   # H Автомобиль
        data["budget"],                # I Бюджет
        data["payment"],               # J Первый взнос
        data["term"],                  # K Срок
        data["guarantors"],            # L Поручители
        data["purchase_time"],         # M План покупки
        data.get("source", "direct"),  # N Источник
        "Новый",                       # O Статус
        "",                            # P Менеджер
        "",                            # Q Комментарий
    ]

    try:
        await asyncio.to_thread(save_lead, row)
    except Exception as exc:
        print(f"Ошибка записи Google Sheets: {exc}")
        await callback.message.answer(
            "Не удалось сохранить заявку из-за технической ошибки. "
            "Попробуйте ещё раз чуть позже или свяжитесь с Акрам Авто по номеру 8 988 038-06-06."
        )
        await callback.answer()
        return

    await callback.message.answer(
        "✅ <b>Заявка успешно принята.</b>\n\n"
        f"Номер заявки: <b>{lead_id}</b>\n\n"
        "Информация передана специалисту. С вами свяжутся для дальнейшей консультации.",
        reply_markup=main_menu(),
    )

    if ADMIN_CHAT_ID != 0:
        manager_text = (
            f"🔥 <b>НОВАЯ ЗАЯВКА №{lead_id}</b>\n\n"
            f"👤 {html.escape(data['name'])}\n"
            f"📱 {html.escape(data['phone'])}\n"
            f"📍 {html.escape(data['city'])}\n\n"
            f"🚘 <b>{html.escape(data['car'])}</b>\n"
            f"💰 Бюджет: {html.escape(data['budget'])}\n"
            f"💳 Первый взнос: {html.escape(data['payment'])}\n"
            f"📅 Срок: {html.escape(data['term'])}\n"
            f"👥 Поручители: {html.escape(data['guarantors'])}\n"
            f"⏱ Покупка: {html.escape(data['purchase_time'])}\n\n"
            f"Источник: {html.escape(data.get('source', 'direct'))}\n"
            f"Telegram: {html.escape(username or 'username отсутствует')}"
        )

        manager_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 Взять в работу", callback_data=f"take:{lead_id}")]
            ]
        )

        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                manager_text,
                reply_markup=manager_keyboard,
            )
        except Exception as exc:
            print(f"Ошибка отправки в чат менеджеров: {exc}")

    source = data.get("source", "direct")
    await state.clear()
    await state.update_data(source=source)
    await callback.answer()


# ============================================================
# MANAGER ACTIONS
# ============================================================

@router.callback_query(F.data.startswith("take:"))
async def take_lead(callback: CallbackQuery) -> None:
    if ADMIN_CHAT_ID == 0 or callback.message.chat.id != ADMIN_CHAT_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    lead_id = callback.data.split(":", 1)[1]
    manager = callback.from_user.full_name

    try:
        ok, current = await asyncio.to_thread(take_lead_in_sheet, lead_id, manager)
    except Exception as exc:
        print(f"Ошибка обновления Google Sheets: {exc}")
        await callback.answer("Ошибка записи в таблицу", show_alert=True)
        return

    if not ok:
        await callback.answer(f"Уже взята: {current}", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ В работе: {manager[:30]}", callback_data="noop")]
        ]
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Заявка закреплена за вами.")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ============================================================
# RUN
# ============================================================

async def main() -> None:
    me = await bot.get_me()
    print(f"Бот @{me.username} запущен")
    print(f"Google-таблица: {spreadsheet.title}")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
