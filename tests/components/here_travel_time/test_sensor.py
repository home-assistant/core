"""The test for the HERE Travel Time sensor platform."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from here_routing import (
    HERERoutingError,
    HERERoutingTooManyRequestsError,
    Place,
    Return,
    RoutingMode,
    Spans,
    TransportMode,
)
from here_transit import (
    HERETransitDepartureArrivalTooCloseError,
    HERETransitNoRouteFoundError,
    HERETransitNoTransitRouteFoundError,
    HERETransitTooManyRequestsError,
)
import pytest

from homeassistant.components.here_travel_time.config_flow import DEFAULT_OPTIONS
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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_TRUCK,
    ROUTE_MODE_FASTEST,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_TRUCK,
)
from homeassistant.components.here_travel_time.coordinator import BACKOFF_MULTIPLIER
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import RESPONSE, TRANSIT_RESPONSE
from .const import (
    API_KEY,
    DEFAULT_CONFIG,
    DESTINATION_LATITUDE,
    DESTINATION_LONGITUDE,
    ORIGIN_LATITUDE,
    ORIGIN_LONGITUDE,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


@pytest.mark.parametrize(
    ("mode", "icon", "arrival_time", "departure_time"),
    [
        (
            TRAVEL_MODE_CAR,
            ICON_CAR,
            None,
            None,
        ),
        (
            TRAVEL_MODE_BICYCLE,
            ICON_BICYCLE,
            None,
            None,
        ),
        (
            TRAVEL_MODE_PEDESTRIAN,
            ICON_PEDESTRIAN,
            None,
            "08:00:00",
        ),
        (
            TRAVEL_MODE_TRUCK,
            ICON_TRUCK,
            None,
            "08:00:00",
        ),
    ],
)
@pytest.mark.usefixtures("valid_response")
async def test_sensor(
    hass: HomeAssistant,
    mode,
    icon,
    arrival_time,
    departure_time,
) -> None:
    """Test that sensor works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: mode,
            CONF_NAME: "test",
        },
        options={
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: arrival_time,
            CONF_DEPARTURE_TIME: departure_time,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    duration = hass.states.get("sensor.test_duration")
    assert duration.attributes.get("unit_of_measurement") == UnitOfTime.MINUTES
    assert duration.attributes.get(ATTR_ICON) == icon
    assert duration.state == "26"

    assert float(hass.states.get("sensor.test_distance").state) == pytest.approx(13.682)
    assert hass.states.get("sensor.test_duration_in_traffic").state == "30"
    assert hass.states.get("sensor.test_origin").state == "22nd St NW"
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LATITUDE)
        == "38.8999937"
    )
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LONGITUDE)
        == "-77.0479682"
    )

    assert hass.states.get("sensor.test_destination").state == "Service Rd S"
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LATITUDE)
        == "38.99997"
    )
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LONGITUDE)
        == "-77.10014"
    )


@pytest.mark.usefixtures("valid_response")
async def test_circular_ref(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "No coordinates found for test.first" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_public_transport(hass: HomeAssistant) -> None:
    """Test that public transport mode is handled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_PUBLIC,
            CONF_NAME: "test",
        },
        options={
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_ARRIVAL_TIME: "08:00:00",
            CONF_DEPARTURE_TIME: None,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_duration").attributes.get(ATTR_ATTRIBUTION)
        == "http://creativecommons.org/licenses/by/3.0/it/,Some line names used in this product or service were edited to align with official transportation maps."
    )
    assert hass.states.get("sensor.test_distance").state == "1.883"


@pytest.mark.usefixtures("no_attribution_response")
async def test_no_attribution_response(hass: HomeAssistant) -> None:
    """Test that no_attribution is handled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_PUBLIC,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_duration").attributes.get(ATTR_ATTRIBUTION) is None
    )


async def test_entity_ids(hass: HomeAssistant, valid_response: MagicMock) -> None:
    """Test that origin/destination supplied by entities works."""
    zone_config = {
        "zone": [
            {
                "name": "Origin",
                "latitude": ORIGIN_LATITUDE,
                "longitude": ORIGIN_LONGITUDE,
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
            "latitude": float(DESTINATION_LATITUDE),
            "longitude": float(DESTINATION_LONGITUDE),
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
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_distance").state == "13.682"

    valid_response.assert_called_with(
        transport_mode=TransportMode.TRUCK,
        origin=Place(ORIGIN_LATITUDE, ORIGIN_LONGITUDE),
        destination=Place(DESTINATION_LATITUDE, DESTINATION_LONGITUDE),
        routing_mode=RoutingMode.FAST,
        arrival_time=None,
        departure_time=None,
        return_values=[Return.POLYINE, Return.SUMMARY],
        spans=[Spans.NAMES],
    )


@pytest.mark.usefixtures("valid_response")
async def test_destination_entity_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a not existing destination_entity_id is caught."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_ENTITY_ID: "device_tracker.test",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "Could not find entity device_tracker.test" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_origin_entity_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a not existing origin_entity_id is caught."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_ENTITY_ID: "device_tracker.test",
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert "Could not find entity device_tracker.test" in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_invalid_destination_entity_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid state of the destination_entity_id is caught."""
    hass.states.async_set(
        "device_tracker.test",
        "test_state",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_ENTITY_ID: "device_tracker.test",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert (
        "device_tracker.test does not have valid coordinates: test_state" in caplog.text
    )


@pytest.mark.usefixtures("valid_response")
async def test_invalid_origin_entity_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_TRUCK,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    assert (
        "device_tracker.test does not have valid coordinates: test_state" in caplog.text
    )


async def test_route_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that route not found error is correctly handled."""
    with patch(
        "here_routing.HERERoutingApi.route",
        side_effect=HERERoutingError(
            "Route calculation failed: Couldn't find a route."
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789",
            data={
                CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
                CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
                CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
                CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_TRUCK,
                CONF_NAME: "test",
            },
            options=DEFAULT_OPTIONS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert "Route calculation failed: Couldn't find a route." in caplog.text


@pytest.mark.usefixtures("valid_response")
async def test_restore_state(hass: HomeAssistant) -> None:
    """Test sensor restore state."""
    # Home assistant is not running yet
    hass.set_state(CoreState.not_running)
    last_reset = "2022-11-29T00:00:00.000000+00:00"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.test_duration",
                    "1234",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfTime.MINUTES,
                        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                    },
                ),
                {
                    "native_value": 1234,
                    "native_unit_of_measurement": UnitOfTime.MINUTES,
                    "icon": "mdi:car",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.test_duration_in_traffic",
                    "5678",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfTime.MINUTES,
                        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                    },
                ),
                {
                    "native_value": 5678,
                    "native_unit_of_measurement": UnitOfTime.MINUTES,
                    "icon": "mdi:car",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.test_distance",
                    "123",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
                        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                    },
                ),
                {
                    "native_value": 123,
                    "native_unit_of_measurement": UnitOfLength.KILOMETERS,
                    "icon": "mdi:car",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.test_origin",
                    "Origin Address 1",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_LATITUDE: ORIGIN_LATITUDE,
                        ATTR_LONGITUDE: ORIGIN_LONGITUDE,
                    },
                ),
                {
                    "native_value": "Origin Address 1",
                    "native_unit_of_measurement": None,
                    ATTR_LATITUDE: ORIGIN_LATITUDE,
                    ATTR_LONGITUDE: ORIGIN_LONGITUDE,
                    "icon": "mdi:store-marker",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.test_destination",
                    "Destination Address 1",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_LATITUDE: DESTINATION_LATITUDE,
                        ATTR_LONGITUDE: DESTINATION_LONGITUDE,
                    },
                ),
                {
                    "native_value": "Destination Address 1",
                    "native_unit_of_measurement": None,
                    "icon": "mdi:store-marker",
                    "last_reset": last_reset,
                },
            ),
        ],
    )

    # create and add entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=DEFAULT_CONFIG, options=DEFAULT_OPTIONS
    )
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("sensor.test_duration")
    assert state.state == "1234"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.MINUTES
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.test_duration_in_traffic")
    assert state.state == "5678"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.MINUTES
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.test_distance")
    assert state.state == "123"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.KILOMETERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.test_origin")
    assert state.state == "Origin Address 1"

    state = hass.states.get("sensor.test_destination")
    assert state.state == "Destination Address 1"


@pytest.mark.parametrize(
    ("exception", "expected_message"),
    [
        (
            HERETransitNoRouteFoundError,
            "Error fetching here_travel_time data",
        ),
        (
            HERETransitNoTransitRouteFoundError,
            "Error fetching here_travel_time data",
        ),
        (
            HERETransitDepartureArrivalTooCloseError,
            "Ignoring HERETransitDepartureArrivalTooCloseError",
        ),
    ],
)
async def test_transit_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, exception, expected_message
) -> None:
    """Test that transit errors are correctly handled."""
    with patch(
        "here_transit.HERETransitApi.route",
        side_effect=exception(),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789",
            data={
                CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
                CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
                CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
                CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_PUBLIC,
                CONF_NAME: "test",
            },
            options=DEFAULT_OPTIONS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert expected_message in caplog.text


async def test_routing_rate_limit(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that rate limiting is applied when encountering HTTP 429."""
    with patch(
        "here_routing.HERERoutingApi.route",
        return_value=RESPONSE,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789",
            data=DEFAULT_CONFIG,
            options=DEFAULT_OPTIONS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.test_distance").state == "13.682"

    with patch(
        "here_routing.HERERoutingApi.route",
        side_effect=HERERoutingTooManyRequestsError(
            "Rate limit for this service has been reached"
        ),
    ):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.test_distance").state == "unavailable"
        assert "Increasing update interval to" in caplog.text

    with patch(
        "here_routing.HERERoutingApi.route",
        return_value=RESPONSE,
    ):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL * BACKOFF_MULTIPLIER + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.test_distance").state == "13.682"
        assert "Resetting update interval to" in caplog.text


async def test_transit_rate_limit(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that rate limiting is applied when encountering HTTP 429."""
    with patch(
        "here_transit.HERETransitApi.route",
        return_value=TRANSIT_RESPONSE,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789",
            data={
                CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
                CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
                CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
                CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_PUBLIC,
                CONF_NAME: "test",
            },
            options=DEFAULT_OPTIONS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.test_distance").state == "1.883"

    with patch(
        "here_transit.HERETransitApi.route",
        side_effect=HERETransitTooManyRequestsError(
            "Rate limit for this service has been reached"
        ),
    ):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.test_distance").state == "unavailable"
        assert "Increasing update interval to" in caplog.text

    with patch(
        "here_transit.HERETransitApi.route",
        return_value=TRANSIT_RESPONSE,
    ):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL * BACKOFF_MULTIPLIER + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.test_distance").state == "1.883"
        assert "Resetting update interval to" in caplog.text


@pytest.mark.usefixtures("bike_response")
async def test_multiple_sections(
    hass: HomeAssistant,
) -> None:
    """Test that multiple sections are handled correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN_LATITUDE: float(ORIGIN_LATITUDE),
            CONF_ORIGIN_LONGITUDE: float(ORIGIN_LONGITUDE),
            CONF_DESTINATION_LATITUDE: float(DESTINATION_LATITUDE),
            CONF_DESTINATION_LONGITUDE: float(DESTINATION_LONGITUDE),
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_BICYCLE,
            CONF_NAME: "test",
        },
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    duration = hass.states.get("sensor.test_duration")
    assert duration.state == "18"

    assert float(hass.states.get("sensor.test_distance").state) == pytest.approx(3.583)
    assert hass.states.get("sensor.test_duration_in_traffic").state == "18"
    assert hass.states.get("sensor.test_origin").state == "Chemin de Halage"
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LATITUDE)
        == "49.1260894"
    )
    assert (
        hass.states.get("sensor.test_origin").attributes.get(ATTR_LONGITUDE)
        == "6.1843356"
    )

    assert hass.states.get("sensor.test_destination").state == "Rue Charles Sadoul"
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LATITUDE)
        == "49.1025668"
    )
    assert (
        hass.states.get("sensor.test_destination").attributes.get(ATTR_LONGITUDE)
        == "6.1768518"
    )
