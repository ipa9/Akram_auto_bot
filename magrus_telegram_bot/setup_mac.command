#!/bin/bash

cd "$(dirname "$0")"

echo ""
echo "======================================"
echo "     УСТАНОВКА MAGRUS TELEGRAM BOT"
echo "======================================"
echo ""

echo "Проверяю наличие Python..."

if ! command -v python3 >/dev/null 2>&1
then
    echo ""
    echo "ОШИБКА: Python 3 не найден."
    echo "Сначала необходимо установить Python 3."
    echo ""
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo ""
echo "Python найден:"
python3 --version

echo ""
echo "Проверяю файлы проекта..."

if [ ! -f "bot.py" ]; then
    echo "ОШИБКА: bot.py не найден."
    read -p "Нажмите Enter..."
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "ОШИБКА: requirements.txt не найден."
    read -p "Нажмите Enter..."
    exit 1
fi

if [ ! -f "service_account.json" ]; then
    echo ""
    echo "ВНИМАНИЕ!"
    echo "service_account.json не найден."
    echo "Google Sheets может не работать."
    echo ""
fi

echo ""
echo "Создаю виртуальное окружение..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
else
    echo ".venv уже существует."
fi

echo ""
echo "Активирую виртуальное окружение..."

source .venv/bin/activate

echo ""
echo "Обновляю pip..."

python -m pip install --upgrade pip

echo ""
echo "Устанавливаю необходимые библиотеки..."
echo ""

python -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "ОШИБКА при установке библиотек."
    echo ""
    read -p "Нажмите Enter..."
    exit 1
fi

echo ""
echo "Проверяю библиотеки..."

python -m pip check

echo ""
echo "Проверяю bot.py..."

python -m py_compile bot.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ОШИБКА в bot.py."
    echo ""
    read -p "Нажмите Enter..."
    exit 1
fi

echo ""
echo "======================================"
echo "       УСТАНОВКА ЗАВЕРШЕНА"
echo "======================================"
echo ""
echo "Теперь можно запустить:"
echo ""
echo "start_mac.command"
echo ""

read -p "Нажмите Enter для завершения..."