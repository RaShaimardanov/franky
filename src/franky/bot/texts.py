"""Все тексты бота — голосом Фрэнки. Разметка HTML, пользовательские данные экранируются.

Фразы взяты из самих эфиров: «Итак, дамы и господа», «Кто я сегодня?», «Господи, храни
сумасшедших», «Удивительное рядом», «Трам-тарарам!», «Шоу-тайм!», «Мысль материальна».
"""

import random
from html import escape

from franky.db.models import Character, Episode, Game, GameStatus
from franky.db.repositories import LeaderboardRow, UserStats
from franky.services.game import Hint, HintKind

BTN_PLAY = "🎭 Кто я сегодня?"
BTN_CATALOG = "📚 Коллекция ролей"
BTN_FAVOURITES = "⭐ Избранное"
BTN_STATS = "📋 Мой диагноз"
BTN_TOP = "🏆 Знатоки"

BTN_GUESS = "🔎 Ваша версия"
BTN_HINT = "💡 Маэстро, намекните!"
BTN_SURRENDER = "🏳 Сдаюсь"
BTN_NEXT = "🎭 Следующая роль"
BTN_SEARCH = "🔎 Найти в коллекции"

# Метка сообщения, выбранного в поиске по каталогу: такое сообщение открывает карточку
# персонажа и никогда не считается ответом на загадку.
CATALOG_MARK = "📚 "
CATALOG_INLINE_PREFIX = "каталог: "

# Описание бота в профиле (setMyDescription, до 512 символов) и короткое (до 120).
BOT_DESCRIPTION = (
    "Silver Rain Radio с гордостью представляет: «Фрэнки-шоу» — прямая трансляция "
    "из сумасшедшего дома!\n\n"
    "2004–2011. Больше двухсот ролей звёздной коллекции: каждую неделю мистер Фрэнки "
    "просыпался кем-то знаменитым и проживал в эфире чужую жизнь, ни разу не назвав имени.\n\n"
    "Ваша задача — угадать, какую. Слушайте выпуск, выдвигайте версию, собирайте "
    "свой диагноз. Господи, храни сумасшедших!"
)
BOT_SHORT_DESCRIPTION = (
    "«Фрэнки-шоу»: слушайте выпуск и угадайте, в какой роли мистер Фрэнки сегодня. "
    "Да у него тысячи лиц!"
)

START = (
    "Кто это?\n"
    "— Это сумасшедший Фрэнки.\n"
    "— И что, он действительно ненормальный?\n"
    "— Он гений. Каждый день в новой роли!\n\n"
    "Итак, дамы и господа! <b>«Фрэнки-шоу»</b> — прямая трансляция из сумасшедшего дома. "
    "Мистер Фрэнки представит вам одну из ролей своей звёздной коллекции. "
    "<b>Ваша задача — угадать, какую.</b>\n\n"
    "🎭 Жмите «{play}» и слушайте.\n"
    "🔎 Версию пишите прямо в чат или ищите имя кнопкой «{guess}».\n"
    "💡 У вас {attempts}, а Маэстро подскажет — но за каждую подсказку "
    "придётся заплатить очками.\n"
    "📚 В «{catalog}» — весь архив с ответами: по фамилиям, по именам "
    "и даже по содержанию.\n\n"
    "Шоу-тайм, дорогие мои!"
)

GAME_CAPTION = (
    "🎭 <b>Кто я сегодня?</b>\n"
    "Внимание, дамы и господа: сегодня я проснулся кем-то знаменитым. "
    "Ваша задача — угадать, какую роль я играю.\n\n"
    "Попыток: {attempts}. Ваша версия, дорогой мой?"
)
GAME_ALREADY_ACTIVE = (
    "О, бог мой, вы же ещё не разгадали меня! Вот она, сегодняшняя роль, ещё раз 👇"
)
NO_EPISODES = "Трам-тарарам! Плёнки ещё не подвезли. Загляните чуть позже, дорогой мой."
AUDIO_FAILED = "Маэстро уронил плёнку 😔 Попробуйте ещё раз чуть позже."
NO_ACTIVE_GAME = f"Сейчас я никого не играю. Жмите «{BTN_PLAY}» — и шоу начнётся!"
NO_MORE_HINTS = "Маэстро больше ничего не скажет. Дальше — только ваша интуиция, дорогой мой."
SEARCH_RESULTS = "Удивительное рядом! Вот кого я нашёл в своей коллекции:"
CONTENT_RESULTS = "А вот выпуски, где об этом шла речь:"
FAVOURITES_EMPTY = (
    "В вашей личной коллекции пока пусто. Отмечайте роли звёздочкой ⭐ после разгадки."
)
FAVOURITES_TITLE = "⭐ <b>Ваша личная коллекция ролей</b> ({total})"
FAV_ADDED = "Роль добавлена в вашу коллекцию ⭐"
FAV_REMOVED = "Роль убрана из коллекции"
CURRENT_RIDDLE = "Это моя сегодняшняя роль — сначала разгадайте её 😉"
ERROR = "О, бог мой, что я говорю? Что-то сломалось. Попробуйте ещё раз чуть позже."
SEARCH_PROMPT = "Ищите прямо из чата — по имени или по содержанию:"

_WRONG = (
    "«{guess}»? Прекрасная версия! Но уверяю вас, всё ещё гораздо более запущено.",
    "«{guess}» — великолепно. Но нет, сегодня я не {guess}.",
    "Спасибо за версию! Но я не {guess}. Глупость, не более.",
    "«{guess}»? Трам-тарарам! Холодно, дорогой мой, холодно.",
)


def start(attempts: int) -> str:
    tries = f"{attempts} {plural(attempts, 'попытка', 'попытки', 'попыток')}"
    return START.format(play=BTN_PLAY, guess=BTN_GUESS, catalog=BTN_CATALOG, attempts=tries)


def game_caption(attempts: int) -> str:
    return GAME_CAPTION.format(attempts=attempts)


def catalog_index(characters: int, episodes: int) -> str:
    return (
        "📚 <b>Звёздная коллекция Фрэнки</b>\n"
        f"{characters} {plural(characters, 'роль', 'роли', 'ролей')}, "
        f"{episodes} {plural(episodes, 'выпуск', 'выпуска', 'выпусков')}. "
        "Да у него тысячи лиц!\n\n"
        "Выбирайте букву фамилии или ищите по имени и по содержанию — "
        "например, «джинн» или «Мулен Руж». Осторожно: здесь все роли с ответами."
    )


def catalog_letter(letter: str, count: int, page: int, pages: int) -> str:
    tail = f" · стр. {page + 1}/{pages}" if pages > 1 else ""
    return f"📚 <b>{escape(letter)}</b> — {count} {plural(count, 'роль', 'роли', 'ролей')}{tail}"


def search_empty(query: str) -> str:
    return (
        f"«{escape(query)}»? Такой роли в моей коллекции нет. "
        "Попробуйте иначе — например, по содержанию выпуска 👇"
    )


def wrong_guess(guess: str, attempts_left: int) -> str:
    phrase = random.choice(_WRONG).format(guess=escape(guess))
    left = f"{attempts_left} {plural(attempts_left, 'попытка', 'попытки', 'попыток')}"
    return f"❌ {phrase}\nОсталось: {left}."


def hint(item: Hint, hints_left: int) -> str:
    match item.kind:
        case HintKind.QUOTE:
            body = f"Маэстро, напомните им мои слова из этого эфира:\n<i>«{escape(item.text)}»</i>"
        case HintKind.YEAR:
            body = f"Эту роль я играл в {escape(item.text)} году. Удивительное рядом!"
        case _:
            what = "Моя фамилия" if item.is_surname else "Моё имя"
            letters = f"{item.letters} {plural(item.letters, 'буква', 'буквы', 'букв')}"
            body = (
                f"Ну хорошо, хорошо… {what} начинается на «{escape(item.text)}», в ней {letters}."
            )
    tail = (
        f"\n\nПодсказок в запасе: {hints_left}." if hints_left else "\n\nБольше Маэстро ни слова."
    )
    return f"💡 {body}{tail}"


def reveal(game: Game) -> str:
    character = game.episode.character
    name = escape(character.name) if character else "—"
    match game.status:
        case GameStatus.WON:
            head = (
                f"✅ <b>Шоу-тайм! Великолепно!</b> Да, сегодня я — <b>{name}</b>.\n"
                f"+{game.score} {_points(game.score)} в ваш диагноз."
            )
        case GameStatus.LOST:
            head = (
                f"🎭 Трам-тарарам! Попытки закончились. Сегодня я был — <b>{name}</b>.\n"
                "Господи, храни сумасшедших!"
            )
        case _:
            head = f"🏳 Сдаётесь? Ну что ж. Сегодня я — <b>{name}</b>."
    details = episode_details(game.episode)
    tail = "\n\nВ какой же роли я явлюсь к вам в следующий раз? Вот загадка."
    return head + (f"\n\n{details}" if details else "") + tail


def episode_details(episode: Episode) -> str:
    lines = []
    if episode.character and episode.character.description:
        lines.append(f"<i>{escape(episode.character.description)}</i>")
    if episode.aired_on:
        lines.append(f"В эфире: {episode.aired_on:%d.%m.%Y}")
    elif episode.aired_year:
        lines.append(f"В эфире: {episode.aired_year}")
    if episode.version:
        lines.append(f"Версия {escape(episode.version)} года")
    return "\n".join(lines)


def episode_caption(episode: Episode) -> str:
    name = episode.character.name if episode.character else episode.title
    details = episode_details(episode)
    return f"🎭 <b>{escape(name)}</b>" + (f"\n{details}" if details else "")


def episode_button(episode: Episode) -> str:
    when = episode.aired_on.strftime("%d.%m.%y") if episode.aired_on else episode.aired_year
    name = episode.character.name if episode.character else episode.title
    return f"{name} · {when}" if when else name


def character_card(character: Character) -> str:
    text = f"🎭 <b>{escape(character.name)}</b>"
    if character.description:
        text += f"\n<i>{escape(character.description)}</i>"
    count = len(character.episodes)
    times = (
        "" if count == 1 else f" — я играл эту роль {count} {plural(count, 'раз', 'раза', 'раз')}"
    )
    return f"{text}\n\nВыпусков в архиве: {count}{times}"


def stats(s: UserStats) -> str:
    accuracy = round(100 * s.wins / s.games) if s.games else 0
    rank = f"\nМесто среди знатоков: {s.rank}" if s.rank else ""
    return (
        "📋 <b>Ваш диагноз</b>\n\n"
        f"Ролей послушано: {s.games}\n"
        f"Разгадано: {s.wins} ({accuracy}%)\n"
        f"Лучшая серия: {s.best_streak}\n"
        f"Очки: {s.score}{rank}\n\n"
        f"<i>{_diagnosis(s)}</i>"
    )


def _diagnosis(s: UserStats) -> str:
    if s.games == 0:
        return "Пока здоровы. Но это ненадолго — шоу далеко не безобидное."
    if s.wins == 0:
        return "Ранняя стадия. Дышите глубже и слушайте внимательнее."
    if s.wins < 10:
        return "Прогрессирующая фрэнкимания. Рекомендовано воскресное прослушивание."
    if s.wins < 50:
        return "Хроническая. Вы уже видите лицо с тысячью лиц."
    return "Неизлечимо. Добро пожаловать во Фрэнки-Лэнд, дорогой мой!"


def leaderboard(rows: list[LeaderboardRow], me: int) -> str:
    if not rows:
        return "🏆 Знатоков пока нет. Станьте первым — шоу-тайм!"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Самые проницательные слушатели</b>\n"]
    for i, row in enumerate(rows, 1):
        name = escape(row.first_name)
        if row.user_id == me:
            name = f"<b>{name}</b>"
        lines.append(f"{medals.get(i, f'{i}.')} {name} — {row.score} {_points(row.score)}")
    return "\n".join(lines)


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _points(n: int) -> str:
    return plural(n, "очко", "очка", "очков")
