"""The test for the HERE Travel Time sensor platform."""
from unittest.mock import patch

from herepy.routing_api import InvalidCredentialsError, NoRouteFoundError
import pytest

from homeassistant.components.here_travel_time.sensor import (
    ATTR_ATTRIBUTION,
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    CONF_MODE,
    CONF_TRAFFIC_MODE,
    CONF_UNIT_SYSTEM,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_PUBLIC,
    ICON_TRUCK,
    NO_ROUTE_ERROR_MESSAGE,
    TIME_MINUTES,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
    TRAVEL_MODES_VEHICLE,
)
from homeassistant.const import ATTR_ICON, EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.here_travel_time.const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)

DOMAIN = "sensor"

PLATFORM = "here_travel_time"


@pytest.mark.parametrize(
    "mode,icon,traffic_mode,unit_system",
    [
        (TRAVEL_MODE_CAR, ICON_CAR, True, "metric"),
        (TRAVEL_MODE_BICYCLE, ICON_BICYCLE, False, "metric"),
        (TRAVEL_MODE_PEDESTRIAN, ICON_PEDESTRIAN, False, "imperial"),
        (TRAVEL_MODE_PUBLIC_TIME_TABLE, ICON_PUBLIC, False, "imperial"),
        (TRAVEL_MODE_TRUCK, ICON_TRUCK, True, "metric"),
    ],
)
async def test_sensor(hass, mode, icon, traffic_mode, unit_system, valid_response):
    """Test that sensor works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "traffic_mode": traffic_mode,
            "unit_system": unit_system,
            "mode": mode,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES
    assert (
        sensor.attributes.get(ATTR_ATTRIBUTION)
        == "With the support of HERE Technologies. All information is provided without warranty of any kind."
    )
    if traffic_mode:
        assert sensor.state == "31"
    else:
        assert sensor.state == "30"

    assert sensor.attributes.get(ATTR_DURATION) == 30.05
    if unit_system == "metric":
        assert sensor.attributes.get(ATTR_DISTANCE) == 23.903
    else:
        assert sensor.attributes.get(ATTR_DISTANCE) == 14.852635608048994
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "US-29 - K St NW; US-29 - Whitehurst Fwy; "
        "I-495 N - Capital Beltway; MD-187 S - Old Georgetown Rd"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == unit_system
    if mode in TRAVEL_MODES_VEHICLE:
        assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 31.016666666666666
    else:
        assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 30.05
    assert sensor.attributes.get(ATTR_ORIGIN) == ",".join(
        [CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_DESTINATION) == ",".join(
        [CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "22nd St NW"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == "Service Rd S"
    assert sensor.attributes.get(CONF_MODE) == mode
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is traffic_mode

    assert sensor.attributes.get(ATTR_ICON) == icon

    # Test traffic mode disabled for vehicles
    if mode in TRAVEL_MODES_VEHICLE:
        assert sensor.attributes.get(ATTR_DURATION) != sensor.attributes.get(
            ATTR_DURATION_IN_TRAFFIC
        )


async def test_entity_ids(hass, valid_response):
    """Test that origin/destination supplied by a zone works."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        zone_config = {
            "zone": [
                {
                    "name": "Destination",
                    "latitude": CAR_DESTINATION_LATITUDE,
                    "longitude": CAR_DESTINATION_LONGITUDE,
                    "radius": 250,
                    "passive": False,
                },
                {
                    "name": "Origin",
                    "latitude": CAR_ORIGIN_LATITUDE,
                    "longitude": CAR_ORIGIN_LONGITUDE,
                    "radius": 250,
                    "passive": False,
                },
            ]
        }
        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_entity_id": "zone.origin",
                "destination_entity_id": "zone.destination",
                "api_key": API_KEY,
                "mode": TRAVEL_MODE_TRUCK,
            }
        }
        assert await async_setup_component(hass, "zone", zone_config)
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        assert sensor.attributes.get(ATTR_DISTANCE) == 23.903


async def test_route_not_found(hass, caplog, valid_response):
    """Test that route not found error is correctly handled."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=NoRouteFoundError,
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert NO_ROUTE_ERROR_MESSAGE in caplog.text


async def test_invalid_credentials(hass, caplog):
    """Test that invalid credentials error is correctly handled."""
    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=InvalidCredentialsError,
    ):
        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_latitude": CAR_ORIGIN_LATITUDE,
                "origin_longitude": CAR_ORIGIN_LONGITUDE,
                "destination_latitude": CAR_DESTINATION_LATITUDE,
                "destination_longitude": CAR_DESTINATION_LONGITUDE,
                "api_key": API_KEY,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert "Invalid credentials" in caplog.text


async def test_arrival(hass, valid_response):
    """Test that arrival works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "arrival": "01:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "30"


async def test_departure(hass, valid_response):
    """Test that departure works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "departure": "23:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "30"


async def test_arrival_only_allowed_for_timetable(hass, caplog):
    """Test that arrival is only allowed when mode is publicTransportTimeTable."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "arrival": "01:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert "[arrival] is an invalid option" in caplog.text


async def test_exclusive_arrival_and_departure(hass, caplog):
    """Test that arrival and departure are exclusive."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "arrival": "01:00:00",
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "departure": "01:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert "two or more values in the same group of exclusion" in caplog.text
