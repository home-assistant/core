"""The test for the here_travel_time sensor platform."""
from unittest.mock import patch

from herepy.routing_api import NoRouteFoundError
import pytest

from homeassistant.components.here_travel_time.const import (
    ARRIVAL_TIME,
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    CONF_ROUTE_MODE,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODE,
    DEPARTURE_TIME,
    DOMAIN,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_PUBLIC,
    ICON_TRUCK,
    NO_ROUTE_ERROR_MESSAGE,
    ROUTE_MODE_FASTEST,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ICON,
    CONF_MODE,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    TIME_MINUTES,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.here_travel_time.const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)


@pytest.fixture(name="failed_response")
def failed_response_fixture():
    """Return failed api response."""
    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=NoRouteFoundError,
    ):
        yield


@pytest.mark.parametrize(
    "mode,icon",
    [
        (TRAVEL_MODE_CAR, ICON_CAR),
        (TRAVEL_MODE_BICYCLE, ICON_BICYCLE),
        (TRAVEL_MODE_PEDESTRIAN, ICON_PEDESTRIAN),
        (TRAVEL_MODE_PUBLIC_TIME_TABLE, ICON_PUBLIC),
        (TRAVEL_MODE_TRUCK, ICON_TRUCK),
    ],
)
async def test_sensor(hass, mode, icon, valid_response):
    """Test that sensor works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            "origin": f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
            "destination": f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
            "api_key": API_KEY,
            "mode": mode,
            "name": "test",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "31"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES
    assert (
        sensor.attributes.get(ATTR_ATTRIBUTION)
        == "With the support of HERE Technologies. All information is provided without warranty of any kind."
    )
    assert sensor.attributes.get(ATTR_DURATION) == 30.05
    assert sensor.attributes.get(ATTR_DISTANCE) == 23.903
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "US-29 - K St NW; US-29 - Whitehurst Fwy; "
        "I-495 N - Capital Beltway; MD-187 S - Old Georgetown Rd"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 31.016666666666666
    assert sensor.attributes.get(ATTR_ORIGIN) == ",".join(
        [CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_DESTINATION) == ",".join(
        [CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "22nd St NW"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == "Service Rd S"
    assert sensor.attributes.get(CONF_MODE) == mode
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is True

    assert sensor.attributes.get(ATTR_ICON) == icon

    # Test traffic mode disabled
    assert sensor.attributes.get(ATTR_DURATION) != sensor.attributes.get(
        ATTR_DURATION_IN_TRAFFIC
    )


@pytest.mark.parametrize(
    "time_type,time",
    [
        (DEPARTURE_TIME, "08:00:00"),
        (DEPARTURE_TIME, "now"),
        (DEPARTURE_TIME, ""),
        (ARRIVAL_TIME, "08:00:00"),
    ],
)
async def test_options(hass, time_type, time, valid_response):
    """Test that different options work."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            "origin": f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
            "destination": f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_CAR,
            "name": "test",
        },
        options={
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_TIME_TYPE: time_type,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME: time,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get(ATTR_DISTANCE) == 14.852635608048994


async def test_entity_ids(hass, valid_response):
    """Test that resolving an entity works."""
    zone_config = {
        "zone": [
            {
                "name": "Destination",
                "latitude": CAR_ORIGIN_LATITUDE,
                "longitude": CAR_ORIGIN_LONGITUDE,
                "radius": 250,
                "passive": False,
            },
            {
                "name": "Origin",
                "latitude": CAR_DESTINATION_LATITUDE,
                "longitude": CAR_DESTINATION_LONGITUDE,
                "radius": 250,
                "passive": False,
            },
        ]
    }
    assert await async_setup_component(hass, "zone", zone_config)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            "origin": "zone.origin",
            "destination": "zone.destination",
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_CAR,
            "name": "test",
        },
        options={
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TIME: "now",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get(ATTR_DISTANCE) == 14.852635608048994


async def test_route_not_found(hass, caplog, failed_response):
    """Test that no route error is logged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            "origin": f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
            "destination": f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_CAR,
            "name": "test",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert NO_ROUTE_ERROR_MESSAGE in caplog.text


async def test_setup_platform(hass, caplog, valid_response):
    """Test that setup platform migration works."""
    config = {
        "sensor": {
            "platform": DOMAIN,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
        }
    }
    with patch(
        "homeassistant.components.here_travel_time.async_setup_entry", return_value=True
    ):
        await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    assert (
        "Your HERE travel time configuration has been imported into the UI"
        in caplog.text
    )
