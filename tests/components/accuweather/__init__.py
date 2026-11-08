"""Tests for AccuWeather."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.core import HomeAssistant


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the AccuWeather integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data={
            "api_key": "32-character-string-1234567890qw",
            "latitude": 55.55,
            "longitude": 122.12,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
