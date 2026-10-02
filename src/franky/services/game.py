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


class HintKind(StrEnum):
    QUOTE = auto()  # цитата из выпуска
    YEAR = auto()  # год эфира
    LETTER = auto()  # первая буква и длина фамилии


@dataclass(frozen=True, slots=True)
class Hint:
    kind: HintKind
    text: str  # цитата, год или буква
    letters: int = 0
    is_surname: bool = False


@dataclass(frozen=True, slots=True)
class HintResult:
    game: Game | None
    hint: Hint | None
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
        hints = await self._hints_for(game)
        if game.hints_used >= len(hints):
            return HintResult(game, None, 0)

        hint = hints[game.hints_used]
        game.hints_used += 1
        return HintResult(game, hint, len(hints) - game.hints_used)

    async def hints_left(self, game: Game) -> int:
        return max(0, len(await self._hints_for(game)) - game.hints_used)

    async def _hints_for(self, game: Game) -> list[Hint]:
        quotes = await self._repos.transcripts.quotes(game.episode_id)
        hints = build_hints(game.episode, self._character_of(game), quotes, seed=game.id)
        return hints[: self._settings.max_hints]

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


def build_hints(
    episode: Episode, character: Character, quotes: list[str], *, seed: int
) -> list[Hint]:
    """Подсказки от самой туманной к самой прямой: цитата → год эфира → первая буква."""
    hints = []
    if quotes:
        hints.append(Hint(HintKind.QUOTE, quotes[seed % len(quotes)]))
    if episode.aired_year:
        hints.append(Hint(HintKind.YEAR, str(episode.aired_year)))
    word = character.surname or character.name
    hints.append(
        Hint(
            HintKind.LETTER,
            word[0].upper(),
            letters=sum(ch.isalpha() for ch in word),
            is_surname=character.surname is not None,
        )
    )
    return hints
