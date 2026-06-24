"""Tests for the Ubiquity airOS integration."""

from airos.airos6 import AirOS6Data
from airos.airos8 import AirOS8Data

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, patch

AirOSData = AirOS8Data | AirOS6Data


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform] | None = None,
) -> None:
    """Fixture for setting up the component."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airos._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
