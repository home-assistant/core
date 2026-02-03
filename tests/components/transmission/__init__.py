"""Tests for Transmission."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


OLD_MOCK_CONFIG_DATA = {
    "name": "Transmission",
    "host": "0.0.0.0",
    "username": "user",
    "password": "pass",
    "port": 9091,
}

MOCK_CONFIG_DATA_VERSION_1_1 = {
    "host": "0.0.0.0",
    "username": "user",
    "password": "pass",
    "port": 9091,
}

MOCK_CONFIG_DATA = {
    "ssl": False,
    "path": "/transmission/rpc",
    "host": "0.0.0.0",
    "username": "user",
    "password": "pass",
    "port": 9091,
}
