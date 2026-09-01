МАГ-РУС TELEGRAM BOT — БЫСТРЫЙ ЗАПУСК

1. Создайте Telegram-бота через @BotFather и получите BOT_TOKEN.
2. Создайте Google Sheets с листом «Заявки» и колонками A:Q:
   ID | Дата | Telegram ID | Username | Имя | Телефон | Город | Автомобиль | Бюджет | Первоначальный взнос | Срок | 2 поручителя | План покупки | Источник | Статус | Менеджер | Комментарий
3. Создайте Service Account в Google Cloud, скачайте JSON-ключ и переименуйте его в service_account.json.
4. Поделитесь Google-таблицей с email из поля client_email этого JSON как «Редактор».
5. Скопируйте ID таблицы из URL между /d/ и /edit.
6. В этой папке скопируйте .env.example в .env и заполните BOT_TOKEN и SHEET_ID.
7. На Mac в Terminal:
   cd /путь/к/magrus_telegram_bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python bot.py
8. Откройте бота и нажмите Start.
9. Создайте закрытую группу менеджеров, добавьте бота, отправьте /chatid, скопируйте ID группы в ADMIN_CHAT_ID в .env и перезапустите бота.

НЕ ПУБЛИКУЙТЕ .env И service_account.json.
