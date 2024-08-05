"""Tests for the solarlog integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up the SolarLog platform."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.solarlog.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


def enabled_devices(key: int | None = None) -> bool | dict[int, bool]:
    """Return enabled devices."""
    data = {0: False, 1: False}
    if key is None:
        return data
    return data.get(key)
