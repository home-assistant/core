"""Tests for the Flexit Nordic (BACnet) integration."""
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_with_selected_platforms(
    hass: HomeAssistant, entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Set up the Flexit Nordic (BACnet) integration with the selected platforms."""
    entry.add_to_hass(hass)
    with patch("homeassistant.components.flexit_bacnet.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
