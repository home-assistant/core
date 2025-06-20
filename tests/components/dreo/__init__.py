"""Test utilities for dreo integration."""

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Initialize integration for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@test.com", CONF_PASSWORD: "test123"},
        unique_id="test@test.com",
    )
    entry.add_to_hass(hass)
    return entry


async def init_integration_with_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Initialize integration with specific entry for testing."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
