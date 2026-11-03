"""Tests for the Motionblinds Bluetooth integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Mock a fully setup config entry."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
