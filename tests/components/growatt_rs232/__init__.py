"""Tests for the growat_rs232 inverter integration."""

from homeassistant.components.growatt_rs232.const import DOMAIN

from .const import CONFIG, DATA_NORMAL, PATCH, TITLE, UNIQUE_ID

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def init_integration(hass) -> MockConfigEntry:
    """Set up the growat_rs232 integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=TITLE, unique_id=UNIQUE_ID, data=CONFIG,
    )
    with patch(
        PATCH, return_value=DATA_NORMAL,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
