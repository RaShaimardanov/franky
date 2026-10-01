import pytest

from franky.config import Settings


def test_empty_env_vars_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT__TOKEN", "42:TEST")
    monkeypatch.setenv("BOT__STORAGE_CHAT_ID", "")
    monkeypatch.setenv("BOT__API_SERVER", "")
    monkeypatch.setenv("GAME__MAX_ATTEMPTS", "")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.bot.storage_chat_id is None
    assert settings.bot.api_server is None
    assert settings.game.max_attempts == 3
