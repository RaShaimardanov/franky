"""Все тексты бота в одном месте. Разметка — HTML, пользовательские данные экранируются."""

from html import escape

from franky.db.models import Character, Episode, Game, GameStatus
from franky.db.repositories import LeaderboardRow, UserStats

BTN_PLAY = "🎧 Новая загадка"
BTN_FAVOURITES = "⭐ Избранное"
BTN_STATS = "📊 Статистика"
BTN_TOP = "🏆 Рейтинг"
BTN_CATALOG = "📚 Каталог"

# Метка сообщения, выбранного в поиске по каталогу: такое сообщение открывает карточку
# персонажа и никогда не считается ответом на загадку.
CATALOG_MARK = "📚 "
CATALOG_INLINE_PREFIX = "каталог: "

START = (
    "Привет! Это архив <b>«Фрэнки-шоу»</b> (2004–2011).\n\n"
    "Каждую неделю ведущий проживал в эфире жизнь одной знаменитости, "
    "не называя её имени, а слушатели угадывали, о ком речь. Теперь угадываешь ты.\n\n"
    "<b>Как играть</b>\n"
    "1. Жми «{play}» и слушай выпуск.\n"
    "2. Напиши, кто это, обычным сообщением или выбери имя через «🔎 Угадать».\n"
    "3. У тебя {attempts} попытки. Подсказки помогут, но съедят очки.\n\n"
    "Вне игры поиск открывает архив: найди персонажа и слушай выпуски с ответом."
)

GAME_CAPTION = (
    "🎧 <b>Кто это?</b>\n"
    "Послушай выпуск и угадай, чью жизнь прожил ведущий.\n"
    "Попыток: {attempts}. Ответ пиши сообщением или жми «🔎 Угадать»."
)
GAME_ALREADY_ACTIVE = "У тебя уже есть неразгаданная загадка — вот она ещё раз 👇"
NO_EPISODES = "Прости, друг, выпусков пока нет. Загляни позже!"
AUDIO_FAILED = "Не получилось отправить выпуск 😔 Попробуй ещё раз чуть позже."
NO_ACTIVE_GAME = f"Сейчас нет активной загадки. Жми «{BTN_PLAY}», чтобы начать."
NO_MORE_HINTS = "Подсказки закончились — дальше только интуиция 🙂"
SEARCH_RESULTS = "Нашлось в архиве:"
FAVOURITES_EMPTY = "В избранном пока пусто. Добавляй выпуски кнопкой ⭐ после разгадки."
FAVOURITES_TITLE = "⭐ <b>Избранное</b> ({total})"
FAV_ADDED = "Добавлено в избранное ⭐"
FAV_REMOVED = "Убрано из избранного"
ERROR = "Что-то пошло не так. Попробуй ещё раз чуть позже."


def start(attempts: int) -> str:
    return START.format(play=BTN_PLAY, attempts=attempts)


def game_caption(attempts: int) -> str:
    return GAME_CAPTION.format(attempts=attempts)


def catalog_index(characters: int, episodes: int) -> str:
    return (
        "📚 <b>Каталог «Фрэнки-шоу»</b>\n"
        f"{characters} {plural(characters, 'персонаж', 'персонажа', 'персонажей')}, "
        f"{episodes} {plural(episodes, 'выпуск', 'выпуска', 'выпусков')}.\n\n"
        "Выбери букву фамилии или найди по имени. Выпуски в каталоге — с ответом, "
        "так что тут можно спойлернуть себе загадку 🙂"
    )


def catalog_letter(letter: str, count: int, page: int, pages: int) -> str:
    tail = f" · стр. {page + 1}/{pages}" if pages > 1 else ""
    return f"📚 <b>{escape(letter)}</b> — {count}{tail}"


def search_empty(query: str) -> str:
    return f"Никого не нашлось по запросу «{escape(query)}». Попробуй иначе или через поиск 👇"


def wrong_guess(guess: str, attempts_left: int) -> str:
    return f"❌ Нет, это не {escape(guess)}. Осталось попыток: {attempts_left}."


def hint(text: str, hints_left: int) -> str:
    tail = f" Осталось подсказок: {hints_left}." if hints_left else " Это была последняя."
    return f"💡 {escape(text)}{tail}"


def reveal(game: Game) -> str:
    character = game.episode.character
    name = escape(character.name) if character else "—"
    match game.status:
        case GameStatus.WON:
            head = f"✅ <b>Верно!</b> Это {name}.\n+{game.score} {_points(game.score)}"
        case GameStatus.LOST:
            head = f"😔 Попытки закончились. Это был(а) <b>{name}</b>."
        case _:
            head = f"🏳 Ответ: <b>{name}</b>."
    return f"{head}\n\n{episode_details(game.episode)}"


def episode_details(episode: Episode) -> str:
    lines = []
    if episode.character and episode.character.description:
        lines.append(f"<i>{escape(episode.character.description)}</i>")
    if episode.aired_on:
        lines.append(f"Эфир: {episode.aired_on:%d.%m.%Y}")
    elif episode.aired_year:
        lines.append(f"Эфир: {episode.aired_year}")
    if episode.version:
        lines.append(f"Версия {escape(episode.version)} года")
    return "\n".join(lines)


def episode_caption(episode: Episode) -> str:
    name = episode.character.name if episode.character else episode.title
    details = episode_details(episode)
    return f"<b>{escape(name)}</b>" + (f"\n{details}" if details else "")


def episode_button(episode: Episode) -> str:
    when = episode.aired_on.strftime("%d.%m.%y") if episode.aired_on else episode.aired_year
    name = episode.character.name if episode.character else episode.title
    return f"{name} · {when}" if when else name


def character_card(character: Character) -> str:
    text = f"<b>{escape(character.name)}</b>"
    if character.description:
        text += f"\n<i>{escape(character.description)}</i>"
    count = len(character.episodes)
    return f"{text}\n\nВыпусков в архиве: {count}"


def stats(s: UserStats) -> str:
    accuracy = round(100 * s.wins / s.games) if s.games else 0
    rank = f"\nМесто в рейтинге: {s.rank}" if s.rank else ""
    return (
        "📊 <b>Твоя статистика</b>\n\n"
        f"Загадок: {s.games}\n"
        f"Угадано: {s.wins} ({accuracy}%)\n"
        f"Лучшая серия: {s.best_streak}\n"
        f"Очки: {s.score}{rank}"
    )


def leaderboard(rows: list[LeaderboardRow], me: int) -> str:
    if not rows:
        return "🏆 Рейтинг пока пуст — стань первым!"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Лучшие знатоки</b>\n"]
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
