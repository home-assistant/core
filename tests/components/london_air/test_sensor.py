"""The tests for the london_air platform."""

from unittest.mock import AsyncMock

from pylondonair import (
    NO_SPECIES_DATA,
    LondonAirConnectionError,
    LondonAirData,
    LondonAirUpdateError,
)
import pytest

from homeassistant.components.london_air.sensor import CONF_LOCATIONS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Merton"]}}


async def test_valid_state(
    hass: HomeAssistant,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test for operational london_air sensor with proper attributes."""
    mock_london_air_client.async_update.return_value = london_air_data
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


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            LondonAirConnectionError("Request to London Air API failed"),
            id="connection-error",
        ),
        pytest.param(
            LondonAirUpdateError("Invalid JSON from London Air API"),
            id="update-error",
        ),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    error: LondonAirConnectionError | LondonAirUpdateError,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test for failure in the API."""
    mock_london_air_client.async_update.side_effect = error
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0


@pytest.mark.parametrize(
    ("location", "entity_id"),
    [
        pytest.param(
            "City of London",
            "sensor.city_of_london",
            id="authority-without-sites",
        ),
        pytest.param(
            "Barking and Dagenham",
            "sensor.barking_and_dagenham",
            id="authority-not-in-data",
        ),
    ],
)
async def test_authority_without_site_data(
    hass: HomeAssistant,
    location: str,
    entity_id: str,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test an authority with no usable site data."""
    config = {"sensor": {"platform": "london_air", CONF_LOCATIONS: [location]}}
    mock_london_air_client.async_update.return_value = london_air_data
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0


async def test_site_without_pollutants(
    hass: HomeAssistant,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test a site that reports no pollutant data."""
    config = {"sensor": {"platform": "london_air", CONF_LOCATIONS: ["Barnet"]}}
    mock_london_air_client.async_update.return_value = london_air_data
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.barnet")
    assert state is not None
    assert state.state == "Low"
    site = state.attributes["data"][0]
    assert site["pollutants"] == [NO_SPECIES_DATA]
    assert site["pollutants_status"] == "no_species_data"
    assert site["number_of_pollutants"] == 0


async def test_second_update_throttled(
    hass: HomeAssistant,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test that a second update within the scan interval does not refetch."""
    mock_london_air_client.async_update.return_value = london_air_data
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()
    assert mock_london_air_client.async_update.await_count == 1

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: "sensor.merton"},
        blocking=True,
    )
    assert mock_london_air_client.async_update.await_count == 1
