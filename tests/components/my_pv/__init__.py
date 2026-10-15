"""The tests for the my-PV component."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ELWA2_SERIAL_NUMBER = "1601500000000000"


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[Platform] | None = None,
) -> None:
    """Set up the my-PV integration, optionally limited to the given platforms."""
    config_entry.add_to_hass(hass)

    if platforms is None:
        await hass.config_entries.async_setup(config_entry.entry_id)
    else:
        with patch("homeassistant.components.my_pv.PLATFORMS", platforms):
            await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
