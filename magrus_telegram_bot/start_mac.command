#!/bin/bash

cd "$(dirname "$0")"

echo ""
echo "======================================"
echo "        MAGRUS TELEGRAM BOT"
echo "======================================"
echo ""

if [ ! -f ".venv/bin/python" ]; then

    echo "Бот ещё не установлен."
    echo ""
    echo "Сначала запустите:"
    echo ""
    echo "setup_mac.command"
    echo ""

    read -p "Нажмите Enter..."
    exit 1
fi

if [ ! -f "bot.py" ]; then

    echo "ОШИБКА: bot.py не найден."

    read -p "Нажмите Enter..."
    exit 1
fi

if [ ! -f "service_account.json" ]; then

    echo "ВНИМАНИЕ: service_account.json не найден."
    echo ""
fi

echo "Запускаю бота..."
echo ""
echo "Для остановки нажмите Control + C."
echo ""
echo "======================================"
echo ""

.venv/bin/python bot.py

echo ""
echo "Бот остановлен."
echo ""

read -p "Нажмите Enter для закрытия..."