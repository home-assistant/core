"""Common fixtures for the Ouman EH-800 tests."""

from collections.abc import Generator
from contextlib import nullcontext
from unittest.mock import AsyncMock, patch

from ouman_eh_800_api import (
    HomeAwayControl,
    L1BaseEndpoints,
    L1ConstantTempMode,
    L1FivePointCurve,
    L1NoRoomSensor,
    L1RoomSensor,
    L1ThreePointCurve,
    L2BaseEndpoints,
    L2FivePointCurve,
    L2NoRoomSensor,
    L2RoomSensor,
    L2ThreePointCurve,
    OperationMode,
    OumanEndpoint,
    OumanRegistry,
    OumanRegistrySet,
    OumanValues,
    PumpSummerStopControl,
    RelayControl,
    RelayL1ValvePosition,
    RelayPumpSummerStop,
    RelayTempDifference,
    RelayTemperature,
    RelayTimeProgram,
    SystemEndpoints,
)
import pytest

from homeassistant.components.ouman_eh_800.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_URL = "http://192.168.1.100"
TEST_USERNAME = "test-user"
TEST_PASSWORD = "test-pass"

# Realistic value for every endpoint the API can return. Each scenario picks
# the subset for its registries, so a single endpoint is defined here once.
_ENDPOINT_VALUES: dict[OumanEndpoint, OumanValues] = {
    # System
    SystemEndpoints.TREND_SAMPLE_INTERVAL: 600.0,
    SystemEndpoints.HOME_AWAY_MODE: HomeAwayControl.HOME,
    SystemEndpoints.OUTSIDE_TEMPERATURE: 0.4,
    SystemEndpoints.RELAY_CONFIGURATION_TYPE: "",
    SystemEndpoints.RELAY_STATUS_TEXT: "Rele ei käytössä",
    SystemEndpoints.L2_INSTALLED_STATUS: "1",
    # L1 base
    L1BaseEndpoints.OPERATION_MODE: OperationMode.AUTOMATIC,
    L1BaseEndpoints.VALVE_POSITION_SETPOINT: 0.0,
    L1BaseEndpoints.WATER_OUT_MIN_TEMP: 12.0,
    L1BaseEndpoints.WATER_OUT_MAX_TEMP: 75.0,
    L1BaseEndpoints.TEMPERATURE_LEVEL_STATUS_TEXT: "L1 Normaalilämpö",
    L1BaseEndpoints.CIRCUIT_NAME: "Patterilämmitys",
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE: 39.1,
    L1BaseEndpoints.VALVE_POSITION: 11.0,
    L1BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE: 41.0,
    L1BaseEndpoints.FINE_ADJUSTMENT_EFFECT: 0.0,
    L1BaseEndpoints.SUPPLY_WATER_TEMPERATURE_SETPOINT: 43.7,
    L1BaseEndpoints.ROOM_SENSOR_INSTALLED: "off",
    # L1 three-point curve
    L1ThreePointCurve.CURVE_MINUS_20_TEMP: 58.0,
    L1ThreePointCurve.CURVE_0_TEMP: 41.0,
    L1ThreePointCurve.CURVE_20_TEMP: 18.0,
    # L1 five-point curve
    L1FivePointCurve.CURVE_MINUS_20_TEMP: 58.0,
    L1FivePointCurve.CURVE_MINUS_10_TEMP: 50.0,
    L1FivePointCurve.CURVE_0_TEMP: 41.0,
    L1FivePointCurve.CURVE_10_TEMP: 30.0,
    L1FivePointCurve.CURVE_20_TEMP: 18.0,
    # L1 no room sensor
    L1NoRoomSensor.TEMPERATURE_DROP: 6.0,
    L1NoRoomSensor.BIG_TEMPERATURE_DROP: 16.0,
    L1NoRoomSensor.ROOM_TEMPERATURE_FINE_TUNING: 0.0,
    # L1 room sensor
    L1RoomSensor.TEMPERATURE_DROP: 1.0,
    L1RoomSensor.BIG_TEMPERATURE_DROP: 3.0,
    L1RoomSensor.ROOM_TEMPERATURE_FINE_TUNING: 0.0,
    L1RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER: 21.0,
    L1RoomSensor.ROOM_SENSOR_POTENTIOMETER: 0.0,
    L1RoomSensor.ROOM_TEMPERATURE: 21.5,
    L1RoomSensor.DELAYED_ROOM_TEMPERATURE: 21.4,
    L1RoomSensor.ROOM_TEMPERATURE_SETPOINT: 21.0,
    # L1 constant temp mode
    L1ConstantTempMode.CONSTANT_TEMP_SETPOINT: 50.0,
    # L2 base
    L2BaseEndpoints.OPERATION_MODE: OperationMode.AUTOMATIC,
    L2BaseEndpoints.VALVE_POSITION_SETPOINT: 0.0,
    L2BaseEndpoints.WATER_OUT_MIN_TEMP: 12.0,
    L2BaseEndpoints.WATER_OUT_MAX_TEMP: 75.0,
    L2BaseEndpoints.TEMPERATURE_LEVEL_STATUS_TEXT: "L2 Normaalilämpö",
    L2BaseEndpoints.CIRCUIT_NAME: "Lattialämmitys",
    L2BaseEndpoints.SUPPLY_WATER_TEMPERATURE: 30.0,
    L2BaseEndpoints.VALVE_POSITION: 5.0,
    L2BaseEndpoints.CURVE_SUPPLY_WATER_TEMPERATURE: 30.0,
    L2BaseEndpoints.DELAYED_OUTDOOR_TEMPERATURE_EFFECT: 0.0,
    L2BaseEndpoints.SUPPLY_WATER_TEMPERATURE_SETPOINT: 30.0,
    L2BaseEndpoints.ROOM_SENSOR_INSTALLED: "on",
    # L2 three-point curve
    L2ThreePointCurve.CURVE_MINUS_20_TEMP: 40.0,
    L2ThreePointCurve.CURVE_0_TEMP: 28.0,
    L2ThreePointCurve.CURVE_20_TEMP: 22.0,
    # L2 five-point curve
    L2FivePointCurve.CURVE_MINUS_20_TEMP: 40.0,
    L2FivePointCurve.CURVE_MINUS_10_TEMP: 35.0,
    L2FivePointCurve.CURVE_0_TEMP: 28.0,
    L2FivePointCurve.CURVE_10_TEMP: 25.0,
    L2FivePointCurve.CURVE_20_TEMP: 22.0,
    # L2 no room sensor
    L2NoRoomSensor.TEMPERATURE_DROP: 6.0,
    L2NoRoomSensor.BIG_TEMPERATURE_DROP: 16.0,
    L2NoRoomSensor.ROOM_TEMPERATURE_FINE_TUNING: 0.0,
    # L2 room sensor
    L2RoomSensor.TEMPERATURE_DROP: 1.0,
    L2RoomSensor.BIG_TEMPERATURE_DROP: 3.0,
    L2RoomSensor.ROOM_TEMPERATURE_FINE_TUNING: 0.0,
    L2RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER: 21.0,
    L2RoomSensor.ROOM_TEMPERATURE: 22.0,
    L2RoomSensor.DELAYED_ROOM_TEMPERATURE: 21.9,
    L2RoomSensor.ROOM_TEMPERATURE_SETPOINT: 21.0,
    # Relay variants (mutually exclusive — at most one per scenario)
    RelayPumpSummerStop.CONTROL: PumpSummerStopControl.AUTO,
    RelayTemperature.CONTROL: RelayControl.AUTO,
    RelayTempDifference.CONTROL: RelayControl.AUTO,
    RelayL1ValvePosition.CONTROL: RelayControl.AUTO,
    RelayTimeProgram.CONTROL: RelayControl.AUTO,
}

# Each scenario is a valid registry set the device may expose. Together they
# cover every endpoint the API can return — both curve types, both room-sensor
# variants on each channel, the additive ConstantTempMode, and all 5 relay
# variants.
SCENARIOS: dict[str, list[type[OumanRegistry]]] = {
    # Realistic combinations
    "room_sensors": [
        SystemEndpoints,
        L1BaseEndpoints,
        L1ThreePointCurve,
        L1RoomSensor,
        L1ConstantTempMode,
        L2BaseEndpoints,
        L2ThreePointCurve,
        L2RoomSensor,
    ],
    "no_room_sensors": [
        SystemEndpoints,
        L1BaseEndpoints,
        L1FivePointCurve,
        L1NoRoomSensor,
        L2BaseEndpoints,
        L2FivePointCurve,
        L2NoRoomSensor,
    ],
    "l1_constant_temp_relay_summer_stop": [
        SystemEndpoints,
        L1BaseEndpoints,
        L1ThreePointCurve,
        L1NoRoomSensor,
        L1ConstantTempMode,
        RelayPumpSummerStop,
    ],
    # Minimal scenarios that wouldn't occur on a real device but test
    # each remaining Relay* registry so every endpoint that the API can
    # return is seen by the integration at least once. They're trimmed
    # to just SystemEndpoints + the relay because a fuller registry set
    # adds no additional coverage here and would only bloat the snapshots.
    "relay_valve_position": [SystemEndpoints, RelayL1ValvePosition],
    "relay_temperature": [SystemEndpoints, RelayTemperature],
    "relay_temp_difference": [SystemEndpoints, RelayTempDifference],
    "relay_time_program": [SystemEndpoints, RelayTimeProgram],
}

_DEFAULT_SCENARIO = "room_sensors"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ouman_eh_800.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="01JABCDEFGHIJKLMNOPQRSTUVW",
        domain=DOMAIN,
        title="Ouman EH-800",
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )


@pytest.fixture(params=[_DEFAULT_SCENARIO])
def scenario(request: pytest.FixtureRequest) -> str:
    """Scenario id; defaults to ``room_sensors`` unless overridden via parametrize."""
    return request.param


@pytest.fixture
def registry_set(scenario: str) -> OumanRegistrySet:
    """The registry set the mocked device exposes for the active scenario."""
    return OumanRegistrySet(registries=SCENARIOS[scenario])


@pytest.fixture
def mock_ouman_client(registry_set: OumanRegistrySet) -> Generator[AsyncMock]:
    """Mock the Ouman EH-800 client for the active scenario."""
    values = {
        endpoint: _ENDPOINT_VALUES[endpoint] for endpoint in registry_set.endpoints
    }
    with (
        patch(
            "homeassistant.components.ouman_eh_800.coordinator.OumanEh800Client",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.ouman_eh_800.config_flow.OumanEh800Client",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_active_registries.return_value = registry_set
        client.get_values.return_value = values

        # Simulate the device: a successful write changes what subsequent
        # reads return, so the coordinator's post-write refresh keeps the
        # new value instead of reverting. The API library parses numeric
        # responses as floats via ``NumberOumanEndpoint.parse_value``, so
        # we mirror that here so int writes round-trip as floats. Tests can
        # override by replacing ``set_endpoint_value.side_effect``.
        def _set_endpoint_value(
            endpoint: OumanEndpoint, value: OumanValues
        ) -> OumanValues:
            stored: OumanValues = float(value) if isinstance(value, int) else value
            values[endpoint] = stored
            return stored

        client.set_endpoint_value.side_effect = _set_endpoint_value
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ouman_client: AsyncMock,
    request: pytest.FixtureRequest,
) -> MockConfigEntry:
    """Set up the Ouman EH-800 integration for testing."""
    mock_config_entry.add_to_hass(hass)

    context = nullcontext()
    if platform := getattr(request, "param", None):
        context = patch("homeassistant.components.ouman_eh_800._PLATFORMS", [platform])

    with context:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
