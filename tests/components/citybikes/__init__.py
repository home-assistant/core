"""Tests for the CityBikes integration."""

from unittest.mock import AsyncMock, Mock

from citybikes import model as citybikes_model

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def setup_integration(
    hass: HomeAssistant,
    mock_citybikes_client: Mock,
    station: citybikes_model.Station,
) -> None:
    """Set up the CityBikes sensor platform for testing."""
    network = citybikes_model.Network.from_dict(
        {
            "id": "mock-network",
            "name": "Mock Network",
            "location": {
                "latitude": 40.0,
                "longitude": -73.0,
                "city": "Test City",
                "country": "US",
            },
            "href": "/v2/networks/mock-network",
            "stations": [station.__dict__],
        }
    )
    mock_citybikes_client.network.return_value.fetch = AsyncMock(return_value=network)

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "citybikes",
                    "network": "mock-network",
                    "stations": ["station-1"],
                }
            ]
        },
    )
    await hass.async_block_till_done()
