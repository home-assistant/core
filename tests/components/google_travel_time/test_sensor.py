"""Test the Google Maps Travel Time sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from google_maps_routing_api import (
    ComputeRoutesResponse,
    GoogleMapsRoutingApiAuthError,
    GoogleMapsRoutingApiError,
    Units,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

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
from homeassistant.const import CONF_MODE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .const import DEFAULT_OPTIONS, MOCK_CONFIG


@pytest.fixture(name="mock_update_empty")
def mock_update_empty_fixture(routes_mock: AsyncMock) -> AsyncMock:
    """Mock an update to the sensor with an empty response."""
    routes_mock.async_compute_routes.return_value = None
    return routes_mock


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("routes_mock", "mock_config")
async def test_sensor(hass: HomeAssistant) -> None:
    """Test that sensor works."""
    assert hass.states.get("sensor.google_travel_time").state == "27.0"
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


@pytest.mark.usefixtures("routes_mock")
async def test_sensor_name_from_entry_title(hass: HomeAssistant) -> None:
    """Test that the sensor name is taken from the config entry title."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home to work",
        data=MOCK_CONFIG,
        options=DEFAULT_OPTIONS,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.google_travel_time_home_to_work"))
    assert state.name == "Google Travel Time Home to work"
    assert state.state == "27.0"


@pytest.mark.usefixtures("mock_update_empty", "mock_config")
@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_empty_response(hass: HomeAssistant) -> None:
    """Test that sensor works for an empty response."""
    assert hass.states.get("sensor.google_travel_time").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_route_without_localized_values(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a route missing the requested optional fields does not raise."""
    routes_mock.async_compute_routes.return_value = ComputeRoutesResponse.from_dict(
        {"routes": [{}]}
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.google_travel_time")
    assert state.state == STATE_UNKNOWN
    assert state.attributes["duration"] == ""
    assert state.attributes["distance"] == ""


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
@pytest.mark.usefixtures("routes_mock", "mock_config")
async def test_sensor_departure_time(hass: HomeAssistant) -> None:
    """Test that sensor works for departure time."""
    assert hass.states.get("sensor.google_travel_time").state == "27.0"


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
@pytest.mark.usefixtures("routes_mock", "mock_config")
async def test_sensor_arrival_time(hass: HomeAssistant) -> None:
    """Test that sensor works for arrival time."""
    assert hass.states.get("sensor.google_travel_time").state == "27.0"


@pytest.mark.parametrize(
    ("unit_system", "expected_unit_option"),
    [
        (METRIC_SYSTEM, Units.METRIC),
        (US_CUSTOMARY_SYSTEM, Units.IMPERIAL),
    ],
)
async def test_sensor_unit_system(
    hass: HomeAssistant,
    routes_mock: AsyncMock,
    unit_system: UnitSystem,
    expected_unit_option: Units,
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
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    routes_mock.async_compute_routes.assert_called_once()
    assert (
        routes_mock.async_compute_routes.call_args.kwargs["units"]
        == expected_unit_option
    )


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that exception gets caught."""
    routes_mock.async_compute_routes.side_effect = GoogleMapsRoutingApiError(
        "Errormessage"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.google_travel_time").state == STATE_UNKNOWN
    assert "Error getting travel time" in caplog.text


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_routes_api_disabled(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that exception gets caught and issue created."""
    routes_mock.async_compute_routes.side_effect = GoogleMapsRoutingApiAuthError(
        "Routes API is disabled.",
        status="PERMISSION_DENIED",
        reason="SERVICE_DISABLED",
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.google_travel_time").state == STATE_UNKNOWN
    assert "Routes API is disabled for this API key" in caplog.text

    assert len(issue_registry.issues) == 1
    issue_id = f"routes_api_disabled_{mock_config.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config.entry_id

    await hass.config_entries.async_remove(mock_config.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
async def test_sensor_auth_error_no_issue(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    routes_mock: AsyncMock,
    mock_config: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a non Routes API disabled auth error does not create an issue."""
    routes_mock.async_compute_routes.side_effect = GoogleMapsRoutingApiAuthError(
        "API key not valid. Please pass a valid API key.",
        reason="API_KEY_INVALID",
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.google_travel_time").state == STATE_UNKNOWN
    assert "Error getting travel time" in caplog.text

    assert not issue_registry.issues
