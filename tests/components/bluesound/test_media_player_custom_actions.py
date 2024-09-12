"""Test custom actions."""

import asyncio
import dataclasses
from unittest.mock import call

from pyblu import PairedPlayer
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import PlayerMocks


async def test_set_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the set sleep timer action."""
    await hass.services.async_call(
        "bluesound",
        "set_sleep_timer",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_called_once()


async def test_clear_sleep_timer(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test the clear sleep timer action."""

    player_mocks.player_data.player.sleep_timer.side_effect = [15, 30, 45, 60, 90, 0]

    await hass.services.async_call(
        "bluesound",
        "clear_sleep_timer",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_has_calls([call()] * 6)


async def test_join_cannot_join_to_self(
    hass: HomeAssistant, setup_config_entry: None, player_mocks: PlayerMocks
) -> None:
    """Test that joining to self is not allowed."""
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            "bluesound",
            "join",
            {
                "entity_id": "media_player.player_name1111",
                "master": "media_player.player_name1111",
            },
            blocking=True,
        )

    assert str(exc.value) == "Cannot join player to itself"


async def test_join(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the join action."""
    await hass.services.async_call(
        "bluesound",
        "join",
        {
            "entity_id": "media_player.player_name1111",
            "master": "media_player.player_name2222",
        },
        blocking=True,
    )

    player_mocks.player_data_secondary.player.add_slave.assert_called_once_with(
        "1.1.1.1", 11000
    )


async def test_unjoin(
    hass: HomeAssistant,
    setup_config_entry: None,
    setup_config_entry_secondary: None,
    player_mocks: PlayerMocks,
) -> None:
    """Test the unjoin action."""
    updated_sync_status = dataclasses.replace(
        player_mocks.player_data.sync_status_store.get(),
        master=PairedPlayer("2.2.2.2", 11000),
    )
    player_mocks.player_data.sync_status_store.set(updated_sync_status)

    # this might be flaky, but we do not have a way to wait for the master to be set
    await asyncio.sleep(0)

    await hass.services.async_call(
        "bluesound",
        "unjoin",
        {"entity_id": "media_player.player_name1111"},
        blocking=True,
    )

    player_mocks.player_data_secondary.player.remove_slave.assert_called_once_with(
        "1.1.1.1", 11000
    )
