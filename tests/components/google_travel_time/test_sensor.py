"""Test the Google Maps Travel Time sensors."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from google.api_core.exceptions import GoogleAPIError
from google.maps.routing_v2 import ComputeRoutesResponse, Route, Units
from google.protobuf import duration_pb2
from google.type import localized_text_pb2
import pytest

from homeassistant.components.google_travel_time.config_flow import default_options
from homeassistant.components.google_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DOMAIN,
    UNITS_METRIC,
)
from homeassistant.components.google_travel_time.sensor import SCAN_INTERVAL
from homeassistant.const import CONF_MODE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .const import DEFAULT_OPTIONS, MOCK_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(name="mock_update")
def mock_update_fixture() -> Generator[AsyncMock]:
    """Mock an update to the sensor."""
    client_mock = AsyncMock()
    client_mock.compute_routes.return_value = ComputeRoutesResponse(
        mapping={
            "routes": [
                Route(
                    mapping={
                        "localized_values": Route.RouteLocalizedValues(
                            mapping={
                                "distance": localized_text_pb2.LocalizedText(
                                    text="21.3 km"
                                ),
                                "duration": localized_text_pb2.LocalizedText(
                                    text="27 mins"
                                ),
                                "static_duration": localized_text_pb2.LocalizedText(
                                    text="26 mins"
                                ),
                            }
                        ),
                        "duration": duration_pb2.Duration(seconds=1620),
                    }
                )
            ]
        }
    )
    with patch(
        "homeassistant.components.google_travel_time.sensor.RoutesAsyncClient",
        return_value=client_mock,
    ):
        yield client_mock.compute_routes


@pytest.fixture(name="mock_update_empty")
def mock_update_empty_fixture(mock_update: AsyncMock) -> AsyncMock:
    """Mock an update to the sensor with an empty response."""
    mock_update.return_value = None
    return mock_update


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor(hass: HomeAssistant) -> None:
    """Test that sensor works."""
    assert hass.states.get("sensor.google_travel_time").state == "27"
    assert (
        hass.states.get("sensor.google_travel_time").attributes["attribution"]
        == "Powered by Google"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration"] == "26 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration_in_traffic"]
        == "27 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["distance"] == "21.3 km"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["origin"] == "location1"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["destination"]
        == "49.983862755708444,8.223882827079068"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["unit_of_measurement"]
        == "min"
    )


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update_empty", "mock_config")
async def test_sensor_empty_response(hass: HomeAssistant) -> None:
    """Test that sensor works for an empty response."""
    assert hass.states.get("sensor.google_travel_time").state == "unknown"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                **DEFAULT_OPTIONS,
                CONF_DEPARTURE_TIME: "10:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_departure_time(hass: HomeAssistant) -> None:
    """Test that sensor works for departure time."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_MODE: "transit",
                CONF_UNITS: UNITS_METRIC,
                CONF_TRANSIT_ROUTING_PREFERENCE: "fewer_transfers",
                CONF_TRANSIT_MODE: "bus",
                CONF_ARRIVAL_TIME: "10:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_arrival_time(hass: HomeAssistant) -> None:
    """Test that sensor works for arrival time."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("unit_system", "expected_unit_option"),
    [
        (METRIC_SYSTEM, Units.METRIC),
        (US_CUSTOMARY_SYSTEM, Units.IMPERIAL),
    ],
)
async def test_sensor_unit_system(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    expected_unit_option: str,
) -> None:
    """Test that sensor works."""
    hass.config.units = unit_system

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options=default_options(hass),
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "google.maps.routing_v2.RoutesAsyncClient.compute_routes"
        ) as compute_routes_mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    compute_routes_mock.assert_called_once()
    assert compute_routes_mock.call_args.args[0].units == expected_unit_option


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_update: AsyncMock,
    mock_config: MockConfigEntry,
) -> None:
    """Test that exception gets caught."""
    mock_update.side_effect = GoogleAPIError("Errormessage")
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert "Error getting travel time" in caplog.text
