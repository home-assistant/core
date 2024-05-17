"""Common methods and const used across tests for FYTA."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

USERNAME = "fyta_user"
PASSWORD = "fyta_pass"
ACCESS_TOKEN = "123xyz"
EXPIRATION = "2030-12-31T10:00:00+00:00"
EXPIRATION_OLD = "2020-01-01T00:00:00+00:00"


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up the Fyta platform."""
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fyta.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
