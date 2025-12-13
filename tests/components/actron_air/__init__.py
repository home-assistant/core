"""Tests for the Actron Air integration."""

from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def add_mock_config(hass: HomeAssistant) -> MockConfigEntry:
    """Create a fake Actron Air Config Entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "test-token"},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
