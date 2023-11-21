"""Testing the functionality of the fire risk data fetcher."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.components.smhi.firerisk.fire_risk_data_fetcher import (
    cities,
    create_smhi_geolocation_events,
    extract_grassfire_info_with_coords,
    fetch_fire_risk_data,
    get_grassfire_risk,
)
from homeassistant.components.smhi.smhi_geolocation_event import SmhiGeolocationEvent

# Sample data returned from the API
sample_api_response = {
    "geometry": {"coordinates": [[17.301084, 60.750685]]},
    "timeSeries": [
        {
            "validTime": "2023-11-21T12:00:00Z",
            "parameters": [
                {
                    "name": "grassfire",
                    "levelType": "forecast",
                    "level": "medium",
                    "values": [3],
                    "unit": "index",
                }
            ],
        }
    ],
}


@pytest.fixture
def mocked_session():
    """Fixture to provide a mock aiohttp.ClientSession."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Create an AsyncMock for the response of the get call
        mock_response = AsyncMock()
        mock_response.json.return_value = sample_api_response
        mock_response.status = 200
        mock_response.raise_for_status.return_value = None

        # Set AsyncMock to the __aenter__ return value of get call
        mock_get.return_value.__aenter__.return_value = mock_response

        yield


@pytest.mark.asyncio
async def test_fetch_fire_risk_data(mocked_session):
    """Test fetch_fire_risk_data function."""
    async with aiohttp.ClientSession() as session:
        result = await fetch_fire_risk_data(session)
        assert isinstance(result, list)
        assert len(result) == len(cities)


@pytest.mark.asyncio
def test_extract_grassfire_info_with_coords():
    """Test extract_grassfire_info_with_coords function."""
    result = extract_grassfire_info_with_coords(sample_api_response)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["validTime"] == "2023-11-21T12:00:00Z"
    assert "coordinates" in result[0]


def test_create_smhi_geolocation_events():
    """Test create_smhi_geolocation_events function."""
    grassfire_risks = extract_grassfire_info_with_coords(sample_api_response)
    result = create_smhi_geolocation_events(grassfire_risks)
    assert all(isinstance(event, SmhiGeolocationEvent) for event in result)


@pytest.mark.asyncio
async def test_get_grassfire_risk(mocked_session):
    """Test get_grassfire_risk function."""
    result = await get_grassfire_risk()
    assert isinstance(result, list)
    assert all(isinstance(event, SmhiGeolocationEvent) for event in result)
