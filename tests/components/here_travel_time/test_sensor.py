"""The test for the here_travel_time sensor platform."""
import urllib

from unittest.mock import patch

from homeassistant.components.here_travel_time.sensor import (
    ATTR_ATTRIBUTION, ATTR_DESTINATION_NAME, ATTR_DISTANCE, ATTR_DURATION,
    ATTR_DURATION_WITHOUT_TRAFFIC, ATTR_ORIGIN_NAME, ATTR_ROUTE, CONF_MODE,
    CONF_TRAFFIC_MODE, CONF_UNIT_SYSTEM, ICON_CAR, ICON_PEDESTRIAN,
    ICON_PUBLIC, ICON_TRUCK, ROUTE_MODE_FASTEST, ROUTE_MODE_SHORTEST,
    SCAN_INTERVAL, TRAFFIC_MODE_DISABLED, TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_CAR, TRAVEL_MODE_PEDESTRIAN, TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_TRUCK, UNIT_OF_MEASUREMENT)
from homeassistant.const import ATTR_ICON
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_time_changed, load_fixture)

DOMAIN = 'sensor'

PLATFORM = 'here_travel_time'

APP_ID = 'test'
APP_CODE = 'test'


def _build_mock_url(origin, destination, modes, app_id, app_code, departure):
    """Construct a url for HERE."""
    base_url = (
        "https://route.cit.api.here.com/routing/7.2/calculateroute.json?")
    parameters = {
        'waypoint0': origin,
        'waypoint1': destination,
        'mode': modes,
        'app_id': app_id,
        'app_code': app_code,
        'departure': departure
    }
    url = base_url + urllib.parse.urlencode(parameters)
    return url


async def test_car(hass, requests_mock):
    """Test that car works."""
    origin = "38.90,-77.04833"
    destination = "39.0,-77.1"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE
    }}

    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.state == '31'
    assert sensor.attributes.get(
        'unit_of_measurement'
        ) == UNIT_OF_MEASUREMENT

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 31.016666666666666
    assert sensor.attributes.get(ATTR_DISTANCE) == 23.903
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "US-29 - K St NW; US-29 - Whitehurst Fwy; "
        "I-495 N - Capital Beltway; MD-187 S - Old Georgetown Rd")
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
    assert sensor.attributes.get(ATTR_DURATION_WITHOUT_TRAFFIC) == 30.05
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == '22nd St NW'
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == 'Service Rd S'
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_CAR
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_CAR


async def test_traffic_mode_disabled(hass, requests_mock):
    """Test that traffic mode disabled works."""
    origin = "38.90,-77.04833"
    destination = "39.0,-77.1"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')

    # Test traffic mode disabled
    assert (
        sensor.attributes.get(ATTR_DURATION) !=
        sensor.attributes.get(ATTR_DURATION_WITHOUT_TRAFFIC)
    )


async def test_traffic_mode_enabled(hass, requests_mock):
    """Test that traffic mode disabled works."""
    origin = "38.90,-77.04833"
    destination = "39.0,-77.1"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_ENABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_enabled_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'traffic_mode': True
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')

    # Test traffic mode enabled
    assert (
        sensor.attributes.get(ATTR_DURATION) !=
        sensor.attributes.get(ATTR_DURATION_WITHOUT_TRAFFIC)
    )


async def test_imperial(hass, requests_mock):
    """Test that imperial units work."""
    origin = "38.90,-77.04833"
    destination = "39.0,-77.1"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'unit_system': 'imperial'
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.attributes.get(ATTR_DISTANCE) == 14.852635608048994


async def test_route_mode_shortest(hass, requests_mock):
    """Test that route mode shortest works."""
    origin = "38.902981,-77.048338"
    destination = "39.042158,-77.119116"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_SHORTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_shortest_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'route_mode': ROUTE_MODE_SHORTEST
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.attributes.get(ATTR_DISTANCE) == 18.388


async def test_route_mode_fastest(hass, requests_mock):
    """Test that route mode fastest works."""
    origin = "38.902981,-77.048338"
    destination = "39.042158,-77.119116"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_ENABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/car_enabled_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'traffic_mode': True
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.attributes.get(ATTR_DISTANCE) == 23.381


async def test_truck(hass, requests_mock):
    """Test that truck works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
    )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'mode': TRAVEL_MODE_TRUCK
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.state == '14'
    assert sensor.attributes.get(
        'unit_of_measurement'
        ) == UNIT_OF_MEASUREMENT

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
    assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "I-190; I-294 S - Tri-State Tollway; I-290 W - Eisenhower Expy W; "
        "IL-64 W - E North Ave; I-290 E - Eisenhower Expy E; I-290"
        )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
    assert sensor.attributes.get(
        ATTR_DURATION_WITHOUT_TRAFFIC
        ) == 13.533333333333333
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ''
    assert sensor.attributes.get(
        ATTR_DESTINATION_NAME
        ) == 'Eisenhower Expy E'
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK


async def test_public_transport(hass, requests_mock):
    """Test that publicTransport works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_PUBLIC, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/public_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'mode': TRAVEL_MODE_PUBLIC
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.state == '89'
    assert sensor.attributes.get(
        'unit_of_measurement'
        ) == UNIT_OF_MEASUREMENT

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 89.16666666666667
    assert sensor.attributes.get(ATTR_DISTANCE) == 22.325
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "332 - Palmer/Schiller; 332 - Cargo Rd./Delta Cargo; "
        "332 - Palmer/Schiller"
        )
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
    assert sensor.attributes.get(
        ATTR_DURATION_WITHOUT_TRAFFIC
        ) == 89.16666666666667
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ''
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_PUBLIC
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_PUBLIC


async def test_pedestrian(hass, requests_mock):
    """Test that pedestrian works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_PEDESTRIAN, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
                    origin,
                    destination,
                    modes,
                    APP_ID,
                    APP_CODE,
                    "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/pedestrian_response.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE,
        'mode': TRAVEL_MODE_PEDESTRIAN
    }}
    assert await async_setup_component(hass, DOMAIN, config)

    sensor = hass.states.get('sensor.test')
    assert sensor.state == '211'
    assert sensor.attributes.get(
        'unit_of_measurement'
        ) == UNIT_OF_MEASUREMENT

    assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
    assert sensor.attributes.get(ATTR_DURATION) == 210.51666666666668
    assert sensor.attributes.get(ATTR_DISTANCE) == 12.533
    assert sensor.attributes.get(ATTR_ROUTE) == (
        "Mannheim Rd; W Belmont Ave; Cullerton St; E Fullerton Ave; "
        "La Porte Ave; E Palmer Ave; N Railroad Ave; W North Ave; "
        "E North Ave; E Third St")
    assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
    assert sensor.attributes.get(
        ATTR_DURATION_WITHOUT_TRAFFIC
        ) == 210.51666666666668
    assert sensor.attributes.get(ATTR_ORIGIN_NAME) == "Mannheim Rd"
    assert sensor.attributes.get(ATTR_DESTINATION_NAME) == ''
    assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_PEDESTRIAN
    assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

    assert sensor.attributes.get(ATTR_ICON) == ICON_PEDESTRIAN


async def test_location_zone(hass, requests_mock):
    """Test that origin/destination supplied by a zone works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
        zone_config = {
            "zone": [
                {
                    'name': 'Destination',
                    'latitude': destination.split(",")[0],
                    'longitude': destination.split(",")[1],
                    'radius': 250,
                    'passive': False
                },
                {
                    'name': 'Origin',
                    'latitude': origin.split(",")[0],
                    'longitude': origin.split(",")[1],
                    'radius': 250,
                    'passive': False
                }
            ]
        }
        assert await async_setup_component(hass, "zone", zone_config)

        config = {DOMAIN: {
            'platform': PLATFORM,
            'name': 'test',
            'origin': "zone.origin",
            'destination': "zone.destination",
            'app_id': APP_ID,
            'app_code': APP_CODE,
            'mode': TRAVEL_MODE_TRUCK
        }}
        assert await async_setup_component(hass, DOMAIN, config)

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'
        assert sensor.attributes.get(
            'unit_of_measurement'
            ) == UNIT_OF_MEASUREMENT

        assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
        assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
        assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
        assert sensor.attributes.get(ATTR_ROUTE) == (
            "I-190; I-294 S - Tri-State Tollway; "
            "I-290 W - Eisenhower Expy W; IL-64 W - E North Ave; "
            "I-290 E - Eisenhower Expy E; I-290")
        assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
        assert sensor.attributes.get(
            ATTR_DURATION_WITHOUT_TRAFFIC
            ) == 13.533333333333333
        assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ''
        assert sensor.attributes.get(
            ATTR_DESTINATION_NAME
            ) == "Eisenhower Expy E"
        assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
        assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

        assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'


async def test_location_sensor(hass, requests_mock):
    """Test that origin/destination supplied by a sensor works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
        hass.states.async_set('sensor.origin', origin)
        hass.states.async_set('sensor.destination', destination)

        config = {DOMAIN: {
            'platform': PLATFORM,
            'name': 'test',
            'origin': "sensor.origin",
            'destination': "sensor.destination",
            'app_id': APP_ID,
            'app_code': APP_CODE,
            'mode': TRAVEL_MODE_TRUCK
        }}
        assert await async_setup_component(hass, DOMAIN, config)

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'
        assert sensor.attributes.get(
            'unit_of_measurement'
            ) == UNIT_OF_MEASUREMENT

        assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
        assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
        assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
        assert sensor.attributes.get(ATTR_ROUTE) == (
            "I-190; I-294 S - Tri-State Tollway; "
            "I-290 W - Eisenhower Expy W; IL-64 W - E North Ave; "
            "I-290 E - Eisenhower Expy E; I-290")
        assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
        assert sensor.attributes.get(
            ATTR_DURATION_WITHOUT_TRAFFIC
            ) == 13.533333333333333
        assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ''
        assert sensor.attributes.get(
            ATTR_DESTINATION_NAME
            ) == 'Eisenhower Expy E'
        assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
        assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

        assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'


async def test_location_person(hass, requests_mock):
    """Test that origin/destination supplied by a person works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
        hass.states.async_set(
            'person.origin',
            "unknown",
            {
                "latitude": float(origin.split(",")[0]),
                "longitude": float(origin.split(",")[1])
            }
        )
        hass.states.async_set(
            'person.destination',
            "unknown",
            {
                "latitude": float(destination.split(",")[0]),
                "longitude": float(destination.split(",")[1])
            }
        )

        config = {DOMAIN: {
            'platform': PLATFORM,
            'name': 'test',
            'origin': "person.origin",
            'destination': "person.destination",
            'app_id': APP_ID,
            'app_code': APP_CODE,
            'mode': TRAVEL_MODE_TRUCK
        }}
        assert await async_setup_component(hass, DOMAIN, config)

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'
        assert sensor.attributes.get(
            'unit_of_measurement'
            ) == UNIT_OF_MEASUREMENT

        assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
        assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
        assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
        assert sensor.attributes.get(ATTR_ROUTE) == (
            "I-190; I-294 S - Tri-State Tollway; "
            "I-290 W - Eisenhower Expy W; IL-64 W - E North Ave; "
            "I-290 E - Eisenhower Expy E; I-290")
        assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
        assert sensor.attributes.get(
            ATTR_DURATION_WITHOUT_TRAFFIC
            ) == 13.533333333333333
        assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ''
        assert sensor.attributes.get(
            ATTR_DESTINATION_NAME
            ) == "Eisenhower Expy E"
        assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
        assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

        assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'


async def test_location_device_tracker(hass, requests_mock):
    """Test that origin/destination supplied by a device_tracker works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
        hass.states.async_set(
            'device_tracker.origin',
            "unknown",
            {
                "latitude": float(origin.split(",")[0]),
                "longitude": float(origin.split(",")[1])
            }
        )
        hass.states.async_set(
            'device_tracker.destination',
            "unknown",
            {
                "latitude": float(destination.split(",")[0]),
                "longitude": float(destination.split(",")[1])
            }
        )

        config = {DOMAIN: {
            'platform': PLATFORM,
            'name': 'test',
            'origin': "device_tracker.origin",
            'destination': "device_tracker.destination",
            'app_id': APP_ID,
            'app_code': APP_CODE,
            'mode': TRAVEL_MODE_TRUCK
        }}
        assert await async_setup_component(hass, DOMAIN, config)

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'
        assert sensor.attributes.get(
            'unit_of_measurement'
            ) == UNIT_OF_MEASUREMENT

        assert sensor.attributes.get(ATTR_ATTRIBUTION) is None
        assert sensor.attributes.get(ATTR_DURATION) == 13.533333333333333
        assert sensor.attributes.get(ATTR_DISTANCE) == 13.049
        assert sensor.attributes.get(ATTR_ROUTE) == (
            "I-190; I-294 S - Tri-State Tollway; "
            "I-290 W - Eisenhower Expy W; IL-64 W - E North Ave; "
            "I-290 E - Eisenhower Expy E; I-290")
        assert sensor.attributes.get(CONF_UNIT_SYSTEM) == 'metric'
        assert sensor.attributes.get(
            ATTR_DURATION_WITHOUT_TRAFFIC
            ) == 13.533333333333333
        assert sensor.attributes.get(ATTR_ORIGIN_NAME) == ''
        assert sensor.attributes.get(
            ATTR_DESTINATION_NAME
            ) == "Eisenhower Expy E"
        assert sensor.attributes.get(CONF_MODE) == TRAVEL_MODE_TRUCK
        assert sensor.attributes.get(CONF_TRAFFIC_MODE) is False

        assert sensor.attributes.get(ATTR_ICON) == ICON_TRUCK

        # Test that update works more than once
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
        await hass.async_block_till_done()

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'


async def test_location_device_tracker_added_after_update(hass, requests_mock):
    """Test that origin/destination supplied by a device_tracker works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    with patch(
        'homeassistant.components.here_travel_time.sensor._LOGGER.error'
    ) as mock_error:
        utcnow = dt_util.utcnow()
        # Patching 'utcnow' to gain more control over the timed update.
        with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
            config = {DOMAIN: {
                'platform': PLATFORM,
                'name': 'test',
                'origin': "device_tracker.origin",
                'destination': "device_tracker.destination",
                'app_id': APP_ID,
                'app_code': APP_CODE,
                'mode': TRAVEL_MODE_TRUCK
            }}
            assert await async_setup_component(hass, DOMAIN, config)

            sensor = hass.states.get('sensor.test')
            assert sensor.state == 'unknown'
            assert mock_error.call_count == 2

            # Device tracker appear after first update
            hass.states.async_set(
                'device_tracker.origin',
                "unknown",
                {
                    "latitude": float(origin.split(",")[0]),
                    "longitude": float(origin.split(",")[1])
                }
            )
            hass.states.async_set(
                'device_tracker.destination',
                "unknown",
                {
                    "latitude": float(destination.split(",")[0]),
                    "longitude": float(destination.split(",")[1])
                }
            )

            # Test that update works more than once
            async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
            await hass.async_block_till_done()

            sensor = hass.states.get('sensor.test')
            assert sensor.state == '14'
            assert mock_error.call_count == 2


async def test_location_device_tracker_in_zone(hass, requests_mock):
    """Test that origin/destination supplied by a device_tracker works."""
    origin = "41.9798,-87.8801"
    destination = "41.9043,-87.9216"
    modes = ";".join(
        [TRAVEL_MODE_TRUCK, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/truck_response.json'
        )
    )
    with patch(
        'homeassistant.components.here_travel_time.sensor._LOGGER.debug'
    ) as mock_debug:
        zone_config = {
            "zone": [
                {
                    'name': 'Origin',
                    'latitude': origin.split(",")[0],
                    'longitude': origin.split(",")[1],
                    'radius': 250,
                    'passive': False
                }
            ]
        }
        assert await async_setup_component(hass, "zone", zone_config)
        hass.states.async_set(
            'device_tracker.origin',
            "origin",
            {
                "latitude": None,
                "longitude": None
            }
        )
        config = {DOMAIN: {
            'platform': PLATFORM,
            'name': 'test',
            'origin': "device_tracker.origin",
            'destination': destination,
            'app_id': APP_ID,
            'app_code': APP_CODE,
            'mode': TRAVEL_MODE_TRUCK
        }}
        assert await async_setup_component(hass, DOMAIN, config)

        sensor = hass.states.get('sensor.test')
        assert sensor.state == '14'
        assert mock_debug.call_count == 1


async def test_route_not_found(hass, requests_mock):
    """Test that route not found error is correctly handled."""
    origin = "52.5160,13.3779"
    destination = "47.013399,-10.171986"
    modes = ";".join(
        [TRAVEL_MODE_CAR, ROUTE_MODE_FASTEST, TRAFFIC_MODE_DISABLED]
        )
    response_url = _build_mock_url(
        origin,
        destination,
        modes,
        APP_ID,
        APP_CODE,
        "now"
        )
    requests_mock.get(
        response_url,
        text=load_fixture(
            'here_travel_time/routing_error_no_route_found.json'
        )
    )

    config = {DOMAIN: {
        'platform': PLATFORM,
        'name': 'test',
        'origin': origin,
        'destination': destination,
        'app_id': APP_ID,
        'app_code': APP_CODE
    }}
    with patch(
        'homeassistant.components.here_travel_time.sensor._LOGGER.error'
    ) as mock_error:
        assert await async_setup_component(hass, DOMAIN, config)
        assert mock_error.call_count == 1
