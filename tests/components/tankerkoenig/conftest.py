"""Fixtures for Tankerkoenig integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tankerkoenig import DOMAIN
from homeassistant.components.tankerkoenig.const import CONF_FUEL_TYPES, CONF_STATIONS
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import NEARBY_STATIONS, PRICES, STATION

from tests.common import MockConfigEntry


@pytest.fixture(name="tankerkoenig")
def mock_tankerkoenig() -> Generator[AsyncMock, None, None]:
    """Mock the aiotankerkoenig client."""
    with patch(
        "homeassistant.components.tankerkoenig.coordinator.Tankerkoenig",
        autospec=True,
    ) as mock_tankerkoenig, patch(
        "homeassistant.components.tankerkoenig.config_flow.Tankerkoenig",
        new=mock_tankerkoenig,
    ):
        mock = mock_tankerkoenig.return_value
        mock.station_details.return_value = STATION
        mock.prices.return_value = PRICES
        mock.nearby_stations.return_value = NEARBY_STATIONS
        yield mock


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mock Title",
        unique_id="51.0_13.0",
        entry_id="8036b4412f2fae6bb9dbab7fe8e37f87",
        options={
            CONF_SHOW_ON_MAP: True,
        },
        data={
            CONF_NAME: "Home",
            CONF_API_KEY: "269534f6-xxxx-xxxx-xxxx-yyyyzzzzxxxx",
            CONF_FUEL_TYPES: ["e5"],
            CONF_LOCATION: {CONF_LATITUDE: 51.0, CONF_LONGITUDE: 13.0},
            CONF_RADIUS: 2.0,
            CONF_STATIONS: [
                "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
            ],
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, tankerkoenig: AsyncMock
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
