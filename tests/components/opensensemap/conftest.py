"""Configure tests for openSenseMap."""
from collections.abc import Awaitable, Callable

import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.core import HomeAssistant

from . import VALID_STATION_ID, VALID_STATION_NAME, patch_opensensemap_get_data

from tests.common import MockConfigEntry

ComponentSetup = Callable[[MockConfigEntry], Awaitable[None]]


@pytest.fixture(name="valid_config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create OpenSky entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=VALID_STATION_NAME,
        data={
            CONF_STATION_ID: VALID_STATION_ID,
        },
        unique_id=VALID_STATION_ID,
    )


@pytest.fixture(name="invalid_config_entry")
def mock_config_entry_invalid_id() -> MockConfigEntry:
    """Create OpenSky entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INVALID STATION",
        data={
            CONF_STATION_ID: "INVALID_ID",
        },
        unique_id="INVALID_ID",
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
) -> Callable[[MockConfigEntry], Awaitable[None]]:
    """Fixture for setting up the component."""

    async def func(mock_config_entry: MockConfigEntry) -> None:
        mock_config_entry.add_to_hass(hass)
        with patch_opensensemap_get_data():
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    return func
