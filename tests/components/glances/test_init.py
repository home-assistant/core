"""Tests for Glances integration."""

from unittest.mock import MagicMock

from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiConnectionError,
    GlancesApiNoDataAvailable,
)
import pytest

from homeassistant.components.glances.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry


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
