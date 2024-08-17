"""Tests for the Epic Games Store helpers."""

from typing import Any

import pytest

from homeassistant.components.epic_games_store.helper import (
    format_game_data,
    get_game_url,
    is_free_game,
)

from .const import (
    DATA_ERROR_ATTRIBUTE_NOT_FOUND,
    DATA_FREE_GAMES_MYSTERY_SPECIAL,
    DATA_FREE_GAMES_ONE,
)

GAMES_TO_TEST_FREE_OR_DISCOUNT = [
    {
        "raw_game_data": DATA_FREE_GAMES_ONE["data"]["Catalog"]["searchStore"][
            "elements"
        ][2],
        "expected_result": True,
    },
    {
        "raw_game_data": DATA_FREE_GAMES_ONE["data"]["Catalog"]["searchStore"][
            "elements"
        ][0],
        "expected_result": False,
    },
    {
        "raw_game_data": DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"][
            "searchStore"
        ]["elements"][1],
        "expected_result": False,
    },
    {
        "raw_game_data": DATA_FREE_GAMES_MYSTERY_SPECIAL["data"]["Catalog"][
            "searchStore"
        ]["elements"][2],
        "expected_result": True,
    },
]


GAMES_TO_TEST_URL = [
    {
        "raw_game_data": DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"][
            "searchStore"
        ]["elements"][1],
        "expected_result": "/p/destiny-2--bungie-30th-anniversary-pack",
    },
    {
        "raw_game_data": DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"][
            "searchStore"
        ]["elements"][4],
        "expected_result": "/bundles/qube-ultimate-bundle",
    },
    {
        "raw_game_data": DATA_ERROR_ATTRIBUTE_NOT_FOUND["data"]["Catalog"][
            "searchStore"
        ]["elements"][5],
        "expected_result": "/p/payday-2-c66369",
    },
    {
        "raw_game_data": DATA_FREE_GAMES_MYSTERY_SPECIAL["data"]["Catalog"][
            "searchStore"
        ]["elements"][2],
        "expected_result": "/p/farming-simulator-22",
    },
]


def test_format_game_data() -> None:
    """Test game data format."""
    game_data = format_game_data(
        GAMES_TO_TEST_FREE_OR_DISCOUNT[0]["raw_game_data"], "fr"
    )
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
            GAMES_TO_TEST_URL[0]["raw_game_data"],
            GAMES_TO_TEST_URL[0]["expected_result"],
        ),
        (
            GAMES_TO_TEST_URL[1]["raw_game_data"],
            GAMES_TO_TEST_URL[1]["expected_result"],
        ),
        (
            GAMES_TO_TEST_URL[2]["raw_game_data"],
            GAMES_TO_TEST_URL[2]["expected_result"],
        ),
        (
            GAMES_TO_TEST_URL[3]["raw_game_data"],
            GAMES_TO_TEST_URL[3]["expected_result"],
        ),
    ],
)
def test_get_game_url(raw_game_data: dict[str, Any], expected_result: bool) -> None:
    """Test to get the game URL."""
    assert get_game_url(raw_game_data, "fr").endswith(expected_result)


@pytest.mark.parametrize(
    ("raw_game_data", "expected_result"),
    [
        (
            GAMES_TO_TEST_FREE_OR_DISCOUNT[0]["raw_game_data"],
            GAMES_TO_TEST_FREE_OR_DISCOUNT[0]["expected_result"],
        ),
        (
            GAMES_TO_TEST_FREE_OR_DISCOUNT[1]["raw_game_data"],
            GAMES_TO_TEST_FREE_OR_DISCOUNT[1]["expected_result"],
        ),
        (
            GAMES_TO_TEST_FREE_OR_DISCOUNT[2]["raw_game_data"],
            GAMES_TO_TEST_FREE_OR_DISCOUNT[2]["expected_result"],
        ),
        (
            GAMES_TO_TEST_FREE_OR_DISCOUNT[3]["raw_game_data"],
            GAMES_TO_TEST_FREE_OR_DISCOUNT[3]["expected_result"],
        ),
    ],
)
def test_is_free_game(raw_game_data: dict[str, Any], expected_result: bool) -> None:
    """Test if this game is free."""
    assert is_free_game(raw_game_data) == expected_result
