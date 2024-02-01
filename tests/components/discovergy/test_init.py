"""Test Discovergy component setup."""
from unittest.mock import AsyncMock

from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("discovergy")
async def test_config_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test for setup success."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (InvalidLogin, ConfigEntryState.SETUP_ERROR),
        (HTTPError, ConfigEntryState.SETUP_RETRY),
        (DiscovergyClientError, ConfigEntryState.SETUP_RETRY),
        (Exception, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    discovergy: AsyncMock,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test for setup failure."""
    config_entry.add_to_hass(hass)

    discovergy.meters.side_effect = error

    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is expected_state


@pytest.mark.usefixtures("setup_integration")
async def test_reload_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry reload."""
    new_data = {"email": "abc@example.com", "password": "password"}

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.config_entries.async_update_entry(config_entry, data=new_data)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == new_data
