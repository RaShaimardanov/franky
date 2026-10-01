"""Игровой процесс: загадка → попытки угадать → результат. Не знает о Telegram."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, auto

from franky.config import GameSettings
from franky.db.models import Character, Episode, Game, GameStatus
from franky.db.repositories import Repos
from franky.domain.guess import is_correct_guess

MAX_SCORE = 3


class NoEpisodesError(Exception):
    """В базе нет ни одного выпуска, готового к отправке."""


class GuessOutcome(StrEnum):
    NO_GAME = auto()
    CORRECT = auto()
    WRONG = auto()
    LOST = auto()


@dataclass(frozen=True, slots=True)
class StartResult:
    game: Game
    episode: Episode
    is_new: bool


@dataclass(frozen=True, slots=True)
class GuessResult:
    outcome: GuessOutcome
    game: Game | None = None
    attempts_left: int = 0


@dataclass(frozen=True, slots=True)
class HintResult:
    game: Game | None
    text: str | None
    hints_left: int


class GameService:
    def __init__(self, repos: Repos, settings: GameSettings) -> None:
        self._repos = repos
        self._settings = settings

    async def start(self, user_id: int) -> StartResult:
        if active := await self._repos.games.active(user_id):
            return StartResult(game=active, episode=active.episode, is_new=False)
        episode = await self._repos.episodes.pick_for_user(user_id)
        if episode is None:
            raise NoEpisodesError
        game = await self._repos.games.create(user_id, episode.id)
        return StartResult(game=game, episode=episode, is_new=True)

    async def cancel(self, game: Game) -> None:
        """Удаляет загадку, которую не удалось показать (например, нет аудиофайла)."""
        await self._repos.session.delete(game)

    async def active(self, user_id: int) -> Game | None:
        return await self._repos.games.active(user_id)

    async def guess(self, user_id: int, text: str) -> GuessResult:
        game = await self._repos.games.active(user_id, for_update=True)
        if game is None:
            return GuessResult(GuessOutcome.NO_GAME)

        character = self._character_of(game)
        correct = is_correct_guess(text, character.aliases, character.surname)
        game.attempts += 1
        await self._repos.games.add_guess(game, text, is_correct=correct)

        if correct:
            wrong = game.attempts - 1
            self._finish(game, GameStatus.WON, score=max(1, MAX_SCORE - wrong - game.hints_used))
            return GuessResult(GuessOutcome.CORRECT, game)

        left = self._settings.max_attempts - game.attempts
        if left <= 0:
            self._finish(game, GameStatus.LOST)
            return GuessResult(GuessOutcome.LOST, game)
        return GuessResult(GuessOutcome.WRONG, game, attempts_left=left)

    async def hint(self, user_id: int) -> HintResult:
        game = await self._repos.games.active(user_id, for_update=True)
        if game is None:
            return HintResult(None, None, 0)
        if game.hints_used >= self._settings.max_hints:
            return HintResult(game, None, 0)

        game.hints_used += 1
        character = self._character_of(game)
        text = build_hint(game.hints_used, game.episode, character)
        return HintResult(game, text, self._settings.max_hints - game.hints_used)

    async def surrender(self, user_id: int) -> Game | None:
        game = await self._repos.games.active(user_id, for_update=True)
        if game:
            self._finish(game, GameStatus.SURRENDERED)
        return game

    @staticmethod
    def _character_of(game: Game) -> Character:
        if game.episode.character is None:
            raise LookupError(f"У выпуска игры {game.id} нет персонажа")
        return game.episode.character

    @staticmethod
    def _finish(game: Game, status: GameStatus, *, score: int = 0) -> None:
        game.status = status
        game.score = score
        game.finished_at = datetime.now(UTC)


def build_hint(number: int, episode: Episode, character: Character) -> str:
    if number == 1:
        if episode.aired_year:
            return f"Выпуск вышел в эфир в {episode.aired_year} году."
        number = 2  # года нет — сразу вторая подсказка
    word = character.surname or character.name
    letters = sum(ch.isalpha() for ch in word)
    what = "Фамилия" if character.surname else "Имя"
    return f"{what} начинается на «{word[0].upper()}», букв в ней — {letters}."
