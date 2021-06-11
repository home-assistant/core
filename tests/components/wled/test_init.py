"""Tests for the WLED integration."""
from unittest.mock import AsyncMock, MagicMock, patch

from wled import WLEDConnectionError

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wled: AsyncMock
) -> None:
    """Test the WLED configuration entry unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


@patch(
    "homeassistant.components.wled.coordinator.WLED.request",
    side_effect=WLEDConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the WLED configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setting_unique_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test we set unique ID if not set yet."""
    assert hass.data[DOMAIN]
    assert init_integration.unique_id == "aabbccddeeff"
