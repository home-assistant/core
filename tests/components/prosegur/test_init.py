"""Tests prosegur setup."""
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN

from .common import setup_platform


async def test_unload_entry(hass):
    """Test unloading the Prosegur entry."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
