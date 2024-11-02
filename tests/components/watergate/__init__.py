"""Tests for the Watergate integration."""

from watergate_local_api.models import DeviceState

from homeassistant.core import HomeAssistant

DEFAULT_DEVICE_STATE = DeviceState(
    "open",
    "on",
    True,
    True,
    "battery",
    "1.0.0",
    100,
    {"volume": 1.2, "duration": 100},
)


async def init_integration(hass: HomeAssistant, mock_entry) -> None:
    """Set up the Watergate integration in Home Assistant."""
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
