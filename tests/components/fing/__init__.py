"""Tests for the Fing integration."""

from unittest.mock import patch

from homeassistant.components.fing.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent
) -> MockConfigEntry:
    """Set up the Mocked Fing integration."""

    entry = MockConfigEntry(domain=DOMAIN, data=mocked_entry)
    with patch(
        "homeassistant.components.fing.coordinator.FingAgent",
        return_value=mocked_fing_agent,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
