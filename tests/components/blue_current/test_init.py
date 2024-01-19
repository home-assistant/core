"""Test Blue Current Init Component."""

from unittest.mock import patch

from bluecurrent_api.exceptions import BlueCurrentException, InvalidApiToken
import pytest

from homeassistant.components.blue_current import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
)

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test load and unload entry."""
    with patch("homeassistant.components.blue_current.Client", autospec=True):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("api_error", "config_error"),
    [
        (InvalidApiToken, ConfigEntryAuthFailed),
        (BlueCurrentException, ConfigEntryNotReady),
    ],
)
async def test_config_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_error: BlueCurrentException,
    config_error: IntegrationError,
) -> None:
    """Test if the correct config error is raised when connecting to the api fails."""
    with patch(
        "homeassistant.components.blue_current.Client.connect",
        side_effect=api_error,
    ), pytest.raises(config_error):
        config_entry.add_to_hass(hass)
        await async_setup_entry(hass, config_entry)
