"""Tests for the Epic Games Store helpers."""

import pytest

from homeassistant.components.epic_games_store.helper import (
    get_country_from_locale,
    is_free_game,
)

from .const import DATA_ONE_FREE_GAME

FREE_GAMES_API = DATA_ONE_FREE_GAME["data"]["Catalog"]["searchStore"]["elements"]
FREE_GAME = FREE_GAMES_API[2]
NOT_FREE_GAME = FREE_GAMES_API[0]


@pytest.mark.parametrize(
    ("locale", "country"),
    [
        ("en-US", "US"),
        ("fr", "FR"),
        ("ja", "JP"),
        ("ko", "KR"),
        ("zh-Hant", "CN"),
    ],
)
async def test_get_country_from_locale(locale: str, country: str) -> None:
    """Test that the country is well created."""
    assert get_country_from_locale(locale) == country


def test_is_free_game() -> None:
    """Test if this game is free."""
    assert is_free_game(FREE_GAME)


def test_is_not_free_game() -> None:
    """Test if this game is not free."""
    assert not is_free_game(NOT_FREE_GAME)
