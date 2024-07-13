"""Tests for the Motionblinds Bluetooth integration."""

from homeassistant.components.motionblinds_ble import async_setup_entry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Mock a fully setup config entry."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await async_setup_entry(hass, mock_config_entry)
    await hass.async_block_till_done()
