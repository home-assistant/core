"""The tests for the london_air platform."""

from unittest.mock import AsyncMock, patch

from pylondonair import LondonAirConnectionError, LondonAirData

from homeassistant.components.london_air.sensor import CONF_LOCATIONS
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}}


async def test_valid_state(hass: HomeAssistant, london_air_data: LondonAirData) -> None:
    """Test for operational london_air sensor with proper attributes."""
    with patch(
        "homeassistant.components.london_air.sensor.LondonAirClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_update = AsyncMock(
            return_value=london_air_data
        )
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["icon"] == "mdi:cloud-outline"
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    assert state.attributes["sites"] == 2
    assert state.attributes["friendly_name"] == "Merton"

    sites = state.attributes["data"]
    assert sites is not None
    assert len(sites) == 2
    assert sites[0]["site_code"] == "ME2"
    assert sites[0]["site_type"] == "Roadside"
    assert sites[0]["site_name"] == "Merton Road"
    assert sites[0]["pollutants_status"] == "Low"

    pollutants = sites[0]["pollutants"]
    assert pollutants is not None
    assert len(pollutants) == 1
    assert pollutants[0]["code"] == "PM10"
    assert pollutants[0]["quality"] == "Low"
    assert int(pollutants[0]["index"]) == 2
    assert pollutants[0]["summary"] == "PM10 is Low"


async def test_api_failure(hass: HomeAssistant) -> None:
    """Test for failure in the API."""
    with patch(
        "homeassistant.components.london_air.sensor.LondonAirClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_update = AsyncMock(
            side_effect=LondonAirConnectionError("Request to London Air API failed")
        )
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0


async def test_authority_without_sites(
    hass: HomeAssistant, london_air_data: LondonAirData
) -> None:
    """Test an authority that reports no sites (e.g. City of London)."""
    config = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["City of London"]}}
    with patch(
        "homeassistant.components.london_air.sensor.LondonAirClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_update = AsyncMock(
            return_value=london_air_data
        )
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.city_of_london")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0
