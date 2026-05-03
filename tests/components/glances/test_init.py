"""Tests for Glances integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiConnectionError,
    GlancesApiNoDataAvailable,
)
import pytest

from homeassistant.components.glances.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Glances is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "entry_state"),
    [
        (GlancesApiAuthorizationError, ConfigEntryState.SETUP_ERROR),
        (GlancesApiConnectionError, ConfigEntryState.SETUP_RETRY),
        (GlancesApiNoDataAvailable, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    error: Exception,
    entry_state: ConfigEntryState,
    mock_api: MagicMock,
) -> None:
    """Test Glances failed due to api error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_api.return_value.get_ha_sensor_data.side_effect = error
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is entry_state


async def test_update_error_includes_message(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: MagicMock,
) -> None:
    """Test that the underlying API error message is propagated to UpdateFailed."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    mock_api.return_value.get_ha_sensor_data.side_effect = GlancesApiConnectionError(
        "Connection to http://localhost:61209/api/4/all failed"
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Connection to http://localhost:61209/api/4/all failed" in str(
        coordinator.last_exception
    )


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Glances."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
