"""Tests for the Epic Games Store helpers."""

from typing import Any

import pytest

from homeassistant.components.epic_games_store.helper import (
    format_game_data,
    get_game_url,
    is_free_game,
)

from .const import DATA_ERROR_ATTRIBUTE_NOT_FOUND, DATA_FREE_GAMES_ONE

FREE_GAMES_API = DATA_FREE_GAMES_ONE["data"]["Catalog"]["searchStore"]["elements"]
FREE_GAME = FREE_GAMES_API[2]
NOT_FREE_GAME = FREE_GAMES_API[0]


def test_format_game_data() -> None:
    """Test game data format."""
    game_data = format_game_data(FREE_GAME, "fr")
    assert game_data
    assert game_data["title"]
    assert game_data["description"]
    assert game_data["released_at"]
    assert game_data["original_price"]
    assert game_data["publisher"]
    assert game_data["url"]
    assert game_data["img_portrait"]
    assert game_data["img_landscape"]
    assert game_data["discount_type"] == "free"
    assert game_data["discount_start_at"]
    assert game_data["discount_end_at"]


@pytest.mark.parametrize(
    ("raw_game_data", "expected_result"),
    [
        (
            DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"]["searchStore"][
                "elements"
            ][1],
            "/p/destiny-2--bungie-30th-anniversary-pack",
        ),
        (
            DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"]["searchStore"][
                "elements"
            ][4],
            "/bundles/qube-ultimate-bundle",
        ),
        (
            DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"]["searchStore"][
                "elements"
            ][5],
            "/p/mystery-game-7",
        ),
    ],
)
def test_get_game_url(raw_game_data: dict[str, Any], expected_result: bool) -> None:
    """Test to get the game URL."""
    assert get_game_url(raw_game_data, "fr").endswith(expected_result)


@pytest.mark.parametrize(
    ("raw_game_data", "expected_result"),
    [
        (FREE_GAME, True),
        (NOT_FREE_GAME, False),
    ],
)
def test_is_free_game(raw_game_data: dict[str, Any], expected_result: bool) -> None:
    """Test if this game is free."""
    assert is_free_game(raw_game_data) == expected_result
