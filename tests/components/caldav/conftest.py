"""Test fixtures for caldav."""
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.caldav.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

UNIQUE_ID = "unique-id-1"


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://example.com/url-1",
            CONF_USERNAME: "username-1",
            CONF_PASSWORD: "password-1",
        },
        unique_id=UNIQUE_ID,
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[str],
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            return result

    return run
