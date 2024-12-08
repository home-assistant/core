"""Tests for the yamaha component."""

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def create_empty_config_entry() -> MockConfigEntry:
    """Create an empty config entry for use in unit tests."""
    data = {CONF_HOST: ""}
    options = {
        "source_ignore": [],
        "source_names": {"AV2": "Screen 2"},
    }

    return MockConfigEntry(
        data=data,
        options=options,
        title="Unit test Yamaha",
        domain="yamaha",
        unique_id="yamaha_unique_id",
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
