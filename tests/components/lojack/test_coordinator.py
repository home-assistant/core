"""Tests for the LoJack coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from lojack_api import ApiError, AuthenticationError

from homeassistant.components.lojack.const import DEFAULT_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


ENTITY_ID = "device_tracker.2021_honda_accord"


async def test_coordinator_update_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity becomes unavailable when coordinator update fails with API error."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"

    mock_device.get_location = AsyncMock(side_effect=ApiError("API unavailable"))

    freezer.tick(timedelta(minutes=DEFAULT_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: MagicMock,
    mock_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entry stays loaded and reauth is triggered on auth error during polling."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_device.get_location = AsyncMock(
        side_effect=AuthenticationError("Token expired")
    )

    freezer.tick(timedelta(minutes=DEFAULT_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entry stays loaded; HA initiates a reauth flow
    assert mock_config_entry.state is ConfigEntryState.LOADED
