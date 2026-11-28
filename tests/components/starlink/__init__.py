"""Tests for the Starlink integration."""

from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.core import HomeAssistant

HISTORY_STATS_FIXTURE = load_json_array_fixture(
    "history_stats_success.json", "starlink"
)
LOCATION_DATA_FIXTURE = load_json_object_fixture(
    "location_data_success.json", "starlink"
)
SLEEP_DATA_FIXTURE = load_json_array_fixture("sleep_data_success.json", "starlink")
STATUS_DATA_FIXTURE = load_json_array_fixture("status_data_success.json", "starlink")


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Starlink integration for testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
