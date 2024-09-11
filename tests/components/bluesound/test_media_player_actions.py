"""Tests for the Bluesound Media Player platform."""

import asyncio
import dataclasses
from unittest.mock import call

from pyblu import Player, Status
from pyblu.errors import PlayerUnreachableError
import pytest

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .utils import ValueStore


async def test_set_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player pause."""
    await hass.services.async_call(
        "bluesound",
        "set_sleep_timer",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.sleep_timer.assert_called_once()


async def test_clear_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player pause."""

    player.sleep_timer.side_effect = [15, 30, 45, 60, 90, 0]

    await hass.services.async_call(
        "bluesound",
        "clear_sleep_timer",
        {"entity_id": "media_player.player_name"},
        blocking=True,
    )

    player.sleep_timer.assert_has_calls([call()] * 6)


async def test_join_cannot_join_to_self(
    hass: HomeAssistant, setup_config_entry: None, player: Player
) -> None:
    """Test the media player pause."""
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            "bluesound",
            "join",
            {
                "entity_id": "media_player.player_name",
                "master": "media_player.player_name",
            },
            blocking=True,
        )

    assert str(exc.value) == "Cannot join player to itself"
