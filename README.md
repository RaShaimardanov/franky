# Фрэнки-шоу 🎧

Telegram-бот-викторина по архиву радиопередачи «Фрэнки-шоу» (2004–2011).

Каждый выпуск ведущий проживал в эфире жизнь одной знаменитости, не называя её имени, а
слушатели угадывали, о ком речь. Бот делает то же самое: присылает выпуск, а ты угадываешь.

## Как это работает

1. **🎧 Новая загадка** (`/play`): бот присылает случайный выпуск, который ты ещё не слышал.
   Название трека нейтральное («Кто я?»), так что ответ не подсмотреть.
2. **Ответ.** Его можно ввести двумя способами:
   - написать имя обычным сообщением. Опечатки, регистр, ё/е и порядок слов прощаются:
     «маяковкий», «В. Маяковский» и «Маяковский Владимир» засчитаются;
   - нажать **🔎 Угадать**: откроется inline-поиск `@бот …` с подсказками имён из архива.
3. **3 попытки**, **2 подсказки** (год эфира, первая буква и длина фамилии) и кнопка «сдаться».
   Очки: `3 − ошибки − подсказки`, минимум 1 за угаданный выпуск.
4. После ответа выпуск можно добавить в **⭐ Избранное**. Есть ещё **📊 Статистика** и **🏆 Рейтинг**.

Вне игры любой текст или inline-запрос работает как **поиск по архиву**. Он находит персонажа
и все его выпуски (у некоторых их несколько, например «вер.2008»), их можно слушать уже с ответом.

## Стек

- Python 3.12+, [aiogram 3](https://docs.aiogram.dev), uv
- PostgreSQL 17 + SQLAlchemy 2 (async) + Alembic; нечёткий поиск через `pg_trgm`
- httpx + BeautifulSoup для импорта каталога с [fshow.info](http://fshow.info)
- rapidfuzz для проверки ответов, structlog для логов
- pytest (включая сквозные тесты бота на настоящем Postgres), ruff, mypy `--strict`

## Структура

```
src/franky/
├── __main__.py          CLI: bot | sync | download | upload
├── config.py            настройки из окружения (.env)
├── domain/              чистая логика без Telegram и БД
│   ├── names.py         разбор «Фамилия, Имя вер.2008 (пояснение)» → персонаж + алиасы
│   └── guess.py         проверка ответа слушателя
├── services/
│   ├── game.py          игровой процесс: старт, попытки, подсказки, очки
│   └── audio.py         отправка аудио (file_id кэшируется в БД)
├── catalog/             импорт архива: парсер страниц, HTTP-клиент, синхронизация
├── db/                  модели, репозитории, сессии, миграции Alembic
└── bot/                 aiogram: роутеры, клавиатуры, тексты, middleware
```

## Деплой (Coolify)

1. **+ New Resource → Public Repository**, URL этого репозитория, ветка, Build Pack: **Docker Compose**.
2. В **Environment Variables** задайте `BOT__TOKEN` и `POSTGRES_PASSWORD` (остальные необязательны,
   см. [.env.example](.env.example)).
3. **Deploy.** Миграции применяются при старте бота.

В [@BotFather](https://t.me/BotFather) включите inline-режим: `/setinline`, иначе кнопка
«🔎 Угадать» работать не будет.

Наполнение каталога: в Coolify откройте **Terminal** контейнера `bot` и выполните

```bash
franky sync      # список выпусков и персонажей с сайта
franky download  # скачать mp3 в том audio
franky upload    # залить аудио в Telegram заранее (нужен BOT__STORAGE_CHAT_ID)
```

Без Coolify всё то же самое: `cp .env.example .env`, `docker compose up -d --build`,
`docker compose exec bot franky sync`.

`sync` идемпотентен, его можно запускать повторно. Файлы называются `<id на сайте>.mp3`,
поэтому уже скачанные выпуски достаточно положить в том `audio` (`/app/data/audio`).

> Bot API принимает файлы до 50 МБ. Если выпуски крупнее, поднимите
> [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) и укажите `BOT__API_SERVER`.

## Локальная разработка

```bash
uv sync
docker run -d --name franky-pg -p 127.0.0.1:5432:5432   -e POSTGRES_USER=franky -e POSTGRES_PASSWORD=change-me -e POSTGRES_DB=franky postgres:17-alpine
uv run alembic upgrade head
uv run franky sync
uv run franky bot
```

Проверки:

```bash
uv run ruff check src/franky tests && uv run mypy -p franky
TEST_DB_DSN=postgresql+asyncpg://franky:change-me@localhost:5432/franky_test uv run pytest
```

Без `TEST_DB_DSN` интеграционные тесты пропускаются, остальные работают без базы.
Новая миграция: `uv run alembic revision --autogenerate -m "..."`.
