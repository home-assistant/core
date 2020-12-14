"""The test for the here_travel_time sensor platform."""
import logging
import urllib

import herepy
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
    ROUTE_MODE_FASTEST,
    ROUTE_MODE_SHORTEST,
    SCAN_INTERVAL,
    TIME_MINUTES,
    TRAFFIC_MODE_DISABLED,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
    convert_time_to_isodate,
)
from homeassistant.const import ATTR_ICON, EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import async_fire_time_changed, load_fixture

DOMAIN = "sensor"

PLATFORM = "here_travel_time"

API_KEY = "test"

TRUCK_ORIGIN_LATITUDE = "41.9798"
TRUCK_ORIGIN_LONGITUDE = "-87.8801"
TRUCK_DESTINATION_LATITUDE = "41.9043"
TRUCK_DESTINATION_LONGITUDE = "-87.9216"

BIKE_ORIGIN_LATITUDE = "41.9798"
BIKE_ORIGIN_LONGITUDE = "-87.8801"
BIKE_DESTINATION_LATITUDE = "41.9043"
BIKE_DESTINATION_LONGITUDE = "-87.9216"

CAR_ORIGIN_LATITUDE = "38.9"
CAR_ORIGIN_LONGITUDE = "-77.04833"
CAR_DESTINATION_LATITUDE = "39.0"
CAR_DESTINATION_LONGITUDE = "-77.1"


def _build_mock_url(origin, destination, modes, api_key, departure=None, arrival=None):
    """Construct a url for HERE."""
    base_url = "https://route.ls.hereapi.com/routing/7.2/calculateroute.json?"
    parameters = {
        "waypoint0": f"geo!{origin}",
        "waypoint1": f"geo!{destination}",
        "mode": ";".join(str(herepy.RouteMode[mode]) for mode in modes),
        "apikey": api_key,
    }
    if arrival is not None:
        parameters["arrival"] = arrival
    if departure is not None:
        parameters["departure"] = departure
    if departure is None and arrival is None:
        parameters["departure"] = "now"
    url = base_url + urllib.parse.urlencode(parameters)
    print(url)
    return url


def _assert_truck_sensor(sensor):
    """Assert that states and attributes are correct for truck_response."""
    assert sensor.state == "14"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
    assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "I-190; I-294 S - Tri-State Tollway; I-290 W - Eisenhower Expy W; "
        "IL-64 W - E North Ave; I-290 E - Eisenhower Expy E; I-290"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 13.533333333333333
    assert sensor.attributes.get(ATTR_ORIGIN) == ",".join(
        [TRUCK_ORIGIN_LATITUDE, TRUCK_ORIGIN_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_DESTINATION) == ",".join(
        [TRUCK_DESTINATION_LATITUDE, TRUCK_DESTINATION_LONGITUDE]
    )
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ""
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == "Eisenhower Expy E"
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK


@pytest.fixture
def requests_mock_credentials_check(requests_mock):
    """Add the url used in the api validation to all requests mock."""
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        ",".join([CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]),
        ",".join([CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]),
        modes,
        API_KEY,
    )
    requests_mock.get(
        response_url, text=load_fixture("here_travel_time/car_response.json")
    )
    return requests_mock


@pytest.fixture
def requests_mock_truck_response(requests_mock_credentials_check):
    """Return a requests_mock for truck respones."""
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_TRUCK, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        ",".join([TRUCK_ORIGIN_LATITUDE, TRUCK_ORIGIN_LONGITUDE]),
        ",".join([TRUCK_DESTINATION_LATITUDE, TRUCK_DESTINATION_LONGITUDE]),
        modes,
        API_KEY,
    )
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/truck_response.json")
    )


@pytest.fixture
def requests_mock_car_disabled_response(requests_mock_credentials_check):
    """Return a requests_mock for truck respones."""
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        ",".join([CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]),
        ",".join([CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]),
        modes,
        API_KEY,
    )
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/car_response.json")
    )


async def test_car(hass, requests_mock_car_disabled_response):
    """Test that car works."""
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

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "30"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES
    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
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
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_CAR
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_CAR

    # Test traffic mode disabled
    assert sensor.attributes.get(ATTR_DURATION) != sensor.attributes.get(
        ATTR_DURATION_IN_TRAFFIC
    )


async def test_traffic_mode_enabled(hass, requests_mock_credentials_check):
    """Test that traffic mode enabled works."""
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_ENABLED]
    response_url = _build_mock_url(
        ",".join([CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]),
        ",".join([CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]),
        modes,
        API_KEY,
    )
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/car_enabled_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "traffic_mode": True,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    # Test traffic mode enabled
    assert sensor.attributes.get(ATTR_DURATION) != sensor.attributes.get(
        ATTR_DURATION_IN_TRAFFIC
    )


async def test_imperial(hass, requests_mock_car_disabled_response):
    """Test that imperial units work."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "unit_system": "imperial",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get(ATTR_DISTANCE) == 14.852635608048994


async def test_route_mode_shortest(hass, requests_mock_credentials_check):
    """Test that route mode shortest works."""
    origin = "38.902981,-77.048338"
    destination = "39.042158,-77.119116"
    modes = [ROUTE_MODE_SHORTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/car_shortest_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "route_mode": ROUTE_MODE_SHORTEST,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get(ATTR_DISTANCE) == 18.388


async def test_route_mode_fastest(hass, requests_mock_credentials_check):
    """Test that route mode fastest works."""
    origin = "38.902981,-77.048338"
    destination = "39.042158,-77.119116"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_ENABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/car_enabled_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "traffic_mode": True,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.attributes.get(ATTR_DISTANCE) == 23.381


async def test_truck(hass, requests_mock_truck_response):
    """Test that truck works."""
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": TRUCK_ORIGIN_LATITUDE,
            "origin_longitude": TRUCK_ORIGIN_LONGITUDE,
            "destination_latitude": TRUCK_DESTINATION_LATITUDE,
            "destination_longitude": TRUCK_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_TRUCK,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    _assert_truck_sensor(sensor)


async def test_public_transport(hass, requests_mock_credentials_check):
    """Test that publicTransport works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_PUBLIC, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/public_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "89"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 89.16666666666667
    assert sensor.attributes.get(ATTR_DISTANCE) == 22.325
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "332 - Palmer/Schiller; 332 - Cargo Rd./Delta Cargo; 332 - Palmer/Schiller"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 89.16666666666667
    assert sensor.attributes.get(ATTR_ORIGIN) == origin
    assert sensor.attributes.get(ATTR_DESTINATION) == destination
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ""
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_PUBLIC
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_PUBLIC


async def test_public_transport_time_table(hass, requests_mock_credentials_check):
    """Test that publicTransportTimeTable works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_PUBLIC_TIME_TABLE, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_travel_time/public_time_table_response.json"),
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "80"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 79.73333333333333
    assert sensor.attributes.get(ATTR_DISTANCE) == 14.775
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "330 - Archer/Harlem (Terminal); 309 - Elmhurst Metra Station"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 79.73333333333333
    assert sensor.attributes.get(ATTR_ORIGIN) == origin
    assert sensor.attributes.get(ATTR_DESTINATION) == destination
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ""
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_PUBLIC_TIME_TABLE
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_PUBLIC


async def test_pedestrian(hass, requests_mock_credentials_check):
    """Test that pedestrian works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_PEDESTRIAN, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/pedestrian_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PEDESTRIAN,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "211"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 210.51666666666668
    assert sensor.attributes.get(ATTR_DISTANCE) == 12.533
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "Mannheim Rd; W Belmont Ave; Cullerton St; E Fullerton Ave; "
        "La Porte Ave; E Palmer Ave; N Railroad Ave; W North Ave; "
        "E North Ave; E Third St"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 210.51666666666668
    assert sensor.attributes.get(ATTR_ORIGIN) == origin
    assert sensor.attributes.get(ATTR_DESTINATION) == destination
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ""
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_PEDESTRIAN
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_PEDESTRIAN


async def test_bicycle(hass, requests_mock_credentials_check):
    """Test that bicycle works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_BICYCLE, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/bike_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_BICYCLE,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "55"
    assert sensor.attributes.get("unit_of_measurement") == TIME_MINUTES

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 54.86666666666667
    assert sensor.attributes.get(ATTR_DISTANCE) == 12.613
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "Mannheim Rd; W Belmont Ave; Cullerton St; N Landen Dr; "
        "E Fullerton Ave; N Wolf Rd; W North Ave; N Clinton Ave; "
        "E Third St; N Caroline Ave"
    )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == "metric"
    assert sensor.attributes.get(ATTR_DURATION_IN_TRAFFIC) == 54.86666666666667
    assert sensor.attributes.get(ATTR_ORIGIN) == origin
    assert sensor.attributes.get(ATTR_DESTINATION) == destination
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ""
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_BICYCLE
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_BICYCLE


async def test_location_zone(hass, requests_mock_truck_response, legacy_patchable_time):
    """Test that origin/destination supplied by a zone works."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        zone_config = {
            "zone": [
                {
                    "name": "Destination",
                    "latitude": TRUCK_DESTINATION_LATITUDE,
                    "longitude": TRUCK_DESTINATION_LONGITUDE,
                    "radius": 250,
                    "passive": False,
                },
                {
                    "name": "Origin",
                    "latitude": TRUCK_ORIGIN_LATITUDE,
                    "longitude": TRUCK_ORIGIN_LONGITUDE,
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
        _assert_truck_sensor(sensor)

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)


async def test_location_sensor(
    hass, requests_mock_truck_response, legacy_patchable_time
):
    """Test that origin/destination supplied by a sensor works."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        hass.states.async_set(
            "sensor.origin", ",".join([TRUCK_ORIGIN_LATITUDE, TRUCK_ORIGIN_LONGITUDE])
        )
        hass.states.async_set(
            "sensor.destination",
            ",".join([TRUCK_DESTINATION_LATITUDE, TRUCK_DESTINATION_LONGITUDE]),
        )

        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_entity_id": "sensor.origin",
                "destination_entity_id": "sensor.destination",
                "api_key": API_KEY,
                "mode": TRAVEL_MODE_TRUCK,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)


async def test_location_person(
    hass, requests_mock_truck_response, legacy_patchable_time
):
    """Test that origin/destination supplied by a person works."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        hass.states.async_set(
            "person.origin",
            "unknown",
            {
                "latitude": float(TRUCK_ORIGIN_LATITUDE),
                "longitude": float(TRUCK_ORIGIN_LONGITUDE),
            },
        )
        hass.states.async_set(
            "person.destination",
            "unknown",
            {
                "latitude": float(TRUCK_DESTINATION_LATITUDE),
                "longitude": float(TRUCK_DESTINATION_LONGITUDE),
            },
        )

        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_entity_id": "person.origin",
                "destination_entity_id": "person.destination",
                "api_key": API_KEY,
                "mode": TRAVEL_MODE_TRUCK,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)


async def test_location_device_tracker(
    hass, requests_mock_truck_response, legacy_patchable_time
):
    """Test that origin/destination supplied by a device_tracker works."""
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        hass.states.async_set(
            "device_tracker.origin",
            "unknown",
            {
                "latitude": float(TRUCK_ORIGIN_LATITUDE),
                "longitude": float(TRUCK_ORIGIN_LONGITUDE),
            },
        )
        hass.states.async_set(
            "device_tracker.destination",
            "unknown",
            {
                "latitude": float(TRUCK_DESTINATION_LATITUDE),
                "longitude": float(TRUCK_DESTINATION_LONGITUDE),
            },
        )

        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_entity_id": "device_tracker.origin",
                "destination_entity_id": "device_tracker.destination",
                "api_key": API_KEY,
                "mode": TRAVEL_MODE_TRUCK,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)


async def test_location_device_tracker_added_after_update(
    hass, requests_mock_truck_response, legacy_patchable_time, caplog
):
    """Test that device_tracker added after first update works."""
    caplog.set_level(logging.ERROR)
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        config = {
            DOMAIN: {
                "platform": PLATFORM,
                "name": "test",
                "origin_entity_id": "device_tracker.origin",
                "destination_entity_id": "device_tracker.destination",
                "api_key": API_KEY,
                "mode": TRAVEL_MODE_TRUCK,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        assert len(caplog.records) == 2
        assert "Unable to find entity" in caplog.text
        caplog.clear()

        # Device tracker appear after first update
        hass.states.async_set(
            "device_tracker.origin",
            "unknown",
            {
                "latitude": float(TRUCK_ORIGIN_LATITUDE),
                "longitude": float(TRUCK_ORIGIN_LONGITUDE),
            },
        )
        hass.states.async_set(
            "device_tracker.destination",
            "unknown",
            {
                "latitude": float(TRUCK_DESTINATION_LATITUDE),
                "longitude": float(TRUCK_DESTINATION_LONGITUDE),
            },
        )

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get("sensor.test")
        _assert_truck_sensor(sensor)
        assert len(caplog.records) == 0


async def test_location_device_tracker_in_zone(
    hass, requests_mock_truck_response, caplog
):
    """Test that device_tracker in zone uses device_tracker state works."""
    caplog.set_level(logging.DEBUG)
    zone_config = {
        "zone": [
            {
                "name": "Origin",
                "latitude": TRUCK_ORIGIN_LATITUDE,
                "longitude": TRUCK_ORIGIN_LONGITUDE,
                "radius": 250,
                "passive": False,
            }
        ]
    }
    assert await async_setup_component(hass, "zone", zone_config)
    hass.states.async_set(
        "device_tracker.origin", "origin", {"latitude": None, "longitude": None}
    )
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_entity_id": "device_tracker.origin",
            "destination_latitude": TRUCK_DESTINATION_LATITUDE,
            "destination_longitude": TRUCK_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_TRUCK,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    _assert_truck_sensor(sensor)
    assert ", getting zone location" in caplog.text


async def test_route_not_found(hass, requests_mock_credentials_check, caplog):
    """Test that route not found error is correctly handled."""
    caplog.set_level(logging.ERROR)
    origin = "52.516,13.3779"
    destination = "47.013399,-10.171986"
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_travel_time/routing_error_no_route_found.json"),
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert len(caplog.records) == 1
    assert NO_ROUTE_ERROR_MESSAGE in caplog.text


async def test_pattern_origin(hass, caplog):
    """Test that pattern matching the origin works."""
    caplog.set_level(logging.ERROR)
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": "138.90",
            "origin_longitude": "-77.04833",
            "destination_latitude": CAR_DESTINATION_LATITUDE,
            "destination_longitude": CAR_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert len(caplog.records) == 2
    assert "invalid latitude" in caplog.text


async def test_pattern_destination(hass, caplog):
    """Test that pattern matching the destination works."""
    caplog.set_level(logging.ERROR)
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": CAR_ORIGIN_LATITUDE,
            "origin_longitude": CAR_ORIGIN_LONGITUDE,
            "destination_latitude": "139.0",
            "destination_longitude": "-77.1",
            "api_key": API_KEY,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert len(caplog.records) == 2
    assert "invalid latitude" in caplog.text


async def test_invalid_credentials(hass, requests_mock, caplog):
    """Test that invalid credentials error is correctly handled."""
    caplog.set_level(logging.ERROR)
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_CAR, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        ",".join([CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE]),
        ",".join([CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE]),
        modes,
        API_KEY,
    )
    requests_mock.get(
        response_url,
        text=load_fixture("here_travel_time/routing_error_invalid_credentials.json"),
    )

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
    assert len(caplog.records) == 1
    assert "Invalid credentials" in caplog.text


async def test_attribution(hass, requests_mock_credentials_check):
    """Test that attributions are correctly displayed."""
    origin = "50.037751372637686,14.39233448220898"
    destination = "50.07993838201255,14.42582157361062"
    modes = [ROUTE_MODE_SHORTEST, TRAVEL_MODE_PUBLIC_TIME_TABLE, TRAFFIC_MODE_ENABLED]
    response_url = _build_mock_url(origin, destination, modes, API_KEY)
    requests_mock_credentials_check.get(
        response_url, text=load_fixture("here_travel_time/attribution_response.json")
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "traffic_mode": True,
            "route_mode": ROUTE_MODE_SHORTEST,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert (
        sensor.attributes.get(ATTR_ATTRIBUTION)
        == "With the support of HERE Technologies. All information is provided without warranty of any kind."
    )


async def test_pattern_entity_state(hass, requests_mock_truck_response, caplog):
    """Test that pattern matching the state of an entity works."""
    caplog.set_level(logging.ERROR)
    hass.states.async_set("sensor.origin", "invalid")

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_entity_id": "sensor.origin",
            "destination_latitude": TRUCK_DESTINATION_LATITUDE,
            "destination_longitude": TRUCK_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_TRUCK,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert len(caplog.records) == 1
    assert "is not a valid set of coordinates" in caplog.text


async def test_pattern_entity_state_with_space(hass, requests_mock_truck_response):
    """Test that pattern matching the state including a space of an entity works."""
    hass.states.async_set(
        "sensor.origin", ", ".join([TRUCK_ORIGIN_LATITUDE, TRUCK_ORIGIN_LONGITUDE])
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_entity_id": "sensor.origin",
            "destination_latitude": TRUCK_DESTINATION_LATITUDE,
            "destination_longitude": TRUCK_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_TRUCK,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_delayed_update(hass, requests_mock_truck_response, caplog):
    """Test that delayed update does not complain about missing entities."""
    caplog.set_level(logging.WARNING)

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_entity_id": "sensor.origin",
            "destination_latitude": TRUCK_DESTINATION_LATITUDE,
            "destination_longitude": TRUCK_DESTINATION_LONGITUDE,
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_TRUCK,
        }
    }
    sensor_config = {
        "sensor": {
            "platform": "template",
            "sensors": [
                {"template_sensor": {"value_template": "{{states('sensor.origin')}}"}}
            ],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "sensor", sensor_config)
    hass.states.async_set(
        "sensor.origin", ",".join([TRUCK_ORIGIN_LATITUDE, TRUCK_ORIGIN_LONGITUDE])
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "Unable to find entity" not in caplog.text


async def test_arrival(hass, requests_mock_credentials_check):
    """Test that arrival works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    arrival = "01:00:00"
    arrival_isodate = convert_time_to_isodate(arrival)
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_PUBLIC_TIME_TABLE, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        origin, destination, modes, API_KEY, arrival=arrival_isodate
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_travel_time/public_time_table_response.json"),
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "arrival": arrival,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "80"


async def test_departure(hass, requests_mock_credentials_check):
    """Test that arrival works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    departure = "23:00:00"
    departure_isodate = convert_time_to_isodate(departure)
    modes = [ROUTE_MODE_FASTEST, TRAVEL_MODE_PUBLIC_TIME_TABLE, TRAFFIC_MODE_DISABLED]
    response_url = _build_mock_url(
        origin, destination, modes, API_KEY, departure=departure_isodate
    )
    requests_mock_credentials_check.get(
        response_url,
        text=load_fixture("here_travel_time/public_time_table_response.json"),
    )

    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "departure": departure,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.test")
    assert sensor.state == "80"


async def test_arrival_only_allowed_for_timetable(hass, caplog):
    """Test that arrival is only allowed when mode is publicTransportTimeTable."""
    caplog.set_level(logging.ERROR)
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "arrival": "01:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert len(caplog.records) == 2
    assert "[arrival] is an invalid option" in caplog.text


async def test_exclusive_arrival_and_departure(hass, caplog):
    """Test that arrival and departure are exclusive."""
    caplog.set_level(logging.ERROR)
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    config = {
        DOMAIN: {
            "platform": PLATFORM,
            "name": "test",
            "origin_latitude": origin.split(",")[0],
            "origin_longitude": origin.split(",")[1],
            "destination_latitude": destination.split(",")[0],
            "destination_longitude": destination.split(",")[1],
            "api_key": API_KEY,
            "arrival": "01:00:00",
            "mode": TRAVEL_MODE_PUBLIC_TIME_TABLE,
            "departure": "01:00:00",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert len(caplog.records) == 2
    assert "two or more values in the same group of exclusion" in caplog.text
