# Resume Bot (Python + MongoDB + Local FS)

Функции:
- Загрузка резюме (PDF/DOCX), извлечение текста
- Бесплатный скоринг (0–100) доступен всем
- Полный отчёт (LLM) только платным, с одним бесплатным показом для бесплатников
- Генерация сопроводительных писем (платно)
- Telegram Payments для пополнения подписки/разблокировки PRO
- Локальное хранение файлов в /data
- MongoDB с админкой (mongo-express)
- Sentry + Prometheus метрики + /healthz
- aiogram 3 (polling)

## Запуск
```bash
cp .env.example .env
# заполняем TELEGRAM_BOT_TOKEN, PAYMENTS_PROVIDER_TOKEN, при желании SENTRY_DSN и LLM_*
docker compose up -d --build
```

- Бот работает в режиме polling.
- Метрики: http://localhost:8000/metrics
- Health: http://localhost:8000/healthz
- Панель БД: http://localhost:8081 (логин/пароль из .env)

## Быстрый тест
1. Напишите боту `/start` и примите соглашение.
2. Отправьте PDF или DOCX.
3. Получите оценку. Для полного отчёта купите PRO (`/buy_pro`) или используйте одноразовый бесплатный показ.
