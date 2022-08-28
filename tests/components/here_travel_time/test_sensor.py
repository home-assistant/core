"""The test for the HERE Travel Time sensor platform."""
from unittest.mock import MagicMock, patch

from herepy.here_enum import RouteMode
from herepy.routing_api import NoRouteFoundError
import pytest

from homeassistant.components.here_travel_time.config_flow import default_options
from homeassistant.components.here_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    CONF_UNIT_SYSTEM,
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
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "mode,icon,unit_system,arrival_time,departure_time,expected_duration,expected_distance,expected_duration_in_traffic",
    [
        (
            TRAVEL_MODE_CAR,
            ICON_CAR,
            "metric",
            None,
            None,
            "30",
            "23.903",
            "31",
        ),
        (
            TRAVEL_MODE_BICYCLE,
            ICON_BICYCLE,
            "metric",
            None,
            None,
            "30",
            "23.903",
            "30",
        ),
        (
            TRAVEL_MODE_PEDESTRIAN,
            ICON_PEDESTRIAN,
            "imperial",
            None,
            None,
            "30",
            "14.852631013",
            "30",
        ),
        (
            TRAVEL_MODE_PUBLIC_TIME_TABLE,
            ICON_PUBLIC,
            "imperial",
            "08:00:00",
            None,
            "30",
            "14.852631013",
            "30",
        ),
        (
            TRAVEL_MODE_TRUCK,
            ICON_TRUCK,
            "metric",
            None,
            "08:00:00",
            "30",
            "23.903",
            "31",
        ),
    ],
)
@pytest.mark.usefixtures("valid_response")
async def test_sensor(
    hass: HomeAssistant,
    mode,
    icon,
    unit_system,
    arrival_time,
    departure_time,
    expected_duration,
    expected_distance,
    expected_duration_in_traffic,
):
    """Test that sensor works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: mode,
            CONF_NAME: "test",
        },
        options={
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: arrival_time,
            CONF_DEPARTURE_TIME: departure_time,
            CONF_UNIT_SYSTEM: unit_system,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    duration = hass.states.get("sensor.test_duration")
    assert duration.attributes.get("unit_of_measurement") == TIME_MINUTES
    assert (
        duration.attributes.get(ATTR_ATTRIBUTION)
        == "With the support of HERE Technologies. All information is provided without warranty of any kind."
    )
    assert duration.attributes.get(ATTR_ICON) == icon
    assert duration.state == expected_duration

    assert (
        hass.states.get("sensor.test_duration_in_traffic").state
        == expected_duration_in_traffic
    )
    assert hass.states.get("sensor.test_distance").state == expected_distance
    assert hass.states.get("sensor.test_route").state == (
        "US-29 - K St NW; US-29 - Whitehurst Fwy; "
        "I-495 N - Capital Beltway; MD-187 S - Old Georgetown Rd"
    )
    assert (
        hass.states.get("sensor.test_duration_in_traffic").state
        == expected_duration_in_traffic
    )
    assert hass.states.get("sensor.test_origin").state == "22nd St NW"
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LATITUDE)
        == CAR_ORIGIN_LATITUDE
    )
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LONGITUDE)
        == CAR_ORIGIN_LONGITUDE
    )

    assert hass.states.get("sensor.test_origin").state == "22nd St NW"
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LATITUDE)
        == CAR_ORIGIN_LATITUDE
    )
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LONGITUDE)
        == CAR_ORIGIN_LONGITUDE
    )

    assert hass.states.get("sensor.test_destination").state == "Service Rd S"
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LATITUDE)
        == CAR_DESTINATION_LATITUDE
    )
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LONGITUDE)
        == CAR_DESTINATION_LONGITUDE
    )


@pytest.mark.usefixtures("valid_response")
async def test_circular_ref(hass: HomeAssistant, caplog):
    """Test that a circular ref is handled."""
    hass.states.async_set(
        "test.first",
        "test.second",
    )
    hass.states.async_set("test.second", "test.first")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_ENTITY_ID: "test.first",
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "No coordinatnes found for test.first" in caplog.text


@pytest.mark.usefixtures("empty_attribution_response")
async def test_no_attribution(hass: HomeAssistant):
    """Test that an empty attribution is handled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_duration").attributes.get(ATTR_ATTRIBUTION) is None
    )


async def test_entity_ids(hass: HomeAssistant, valid_response: MagicMock):
    """Test that origin/destination supplied by entities works."""
    zone_config = {
        "zone": [
            {
                "name": "Origin",
                "latitude": CAR_ORIGIN_LATITUDE,
                "longitude": CAR_ORIGIN_LONGITUDE,
                "radius": 250,
                "passive": False,
            },
        ]
    }
    assert await async_setup_component(hass, "zone", zone_config)
    hass.states.async_set(
        "device_tracker.test",
        "not_home",
        {
            "latitude": float(CAR_DESTINATION_LATITUDE),
            "longitude": float(CAR_DESTINATION_LONGITUDE),
        },
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_ENTITY_ID: "zone.origin",
            CONF_DESTINATION_ENTITY_ID: "device_tracker.test",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_distance").state == "23.903"

    valid_response.assert_called_with(
        [CAR_ORIGIN_LATITUDE, CAR_ORIGIN_LONGITUDE],
        [CAR_DESTINATION_LATITUDE, CAR_DESTINATION_LONGITUDE],
        True,
        [
            RouteMode[ROUTE_MODE_FASTEST],
            RouteMode[TRAVEL_MODE_TRUCK],
            RouteMode[TRAFFIC_MODE_ENABLED],
        ],
        arrival=None,
        departure="now",
    )


@pytest.mark.usefixtures("valid_response")
async def test_destination_entity_not_found(hass: HomeAssistant, caplog):
    """Test that a not existing destination_entity_id is caught."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_ENTITY_ID: "device_tracker.test",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "device_tracker.test are not valid coordinates" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_origin_entity_not_found(hass: HomeAssistant, caplog):
    """Test that a not existing origin_entity_id is caught."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_ENTITY_ID: "device_tracker.test",
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "device_tracker.test are not valid coordinates" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_invalid_destination_entity_state(hass: HomeAssistant, caplog):
    """Test that an invalid state of the destination_entity_id is caught."""
    hass.states.async_set(
        "device_tracker.test",
        "test_state",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
            CONF_DESTINATION_ENTITY_ID: "device_tracker.test",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "test_state are not valid coordinates" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_invalid_origin_entity_state(hass: HomeAssistant, caplog):
    """Test that an invalid state of the origin_entity_id is caught."""
    hass.states.async_set(
        "device_tracker.test",
        "test_state",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_ENTITY_ID: "device_tracker.test",
            CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=default_options(hass),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "test_state are not valid coordinates" in caplog.text


async def test_route_not_found(hass: HomeAssistant, caplog):
    """Test that route not found error is correctly handled."""
    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=NoRouteFoundError,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789",
            data={
                CONF_ORIGIN_LATITUDE: float(CAR_ORIGIN_LATITUDE),
                CONF_ORIGIN_LONGITUDE: float(CAR_ORIGIN_LONGITUDE),
                CONF_DESTINATION_LATITUDE: float(CAR_DESTINATION_LATITUDE),
                CONF_DESTINATION_LONGITUDE: float(CAR_DESTINATION_LONGITUDE),
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_TRUCK,
                CONF_NAME: "test",
            },
            options=default_options(hass),
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert NO_ROUTE_ERROR_MESSAGE in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_setup_platform(hass: HomeAssistant, caplog):
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
