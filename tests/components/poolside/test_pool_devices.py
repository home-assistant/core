"""Tests for pool device sub-devices and their InformationFields sensors."""

import json
from typing import Any

from aiopoolside import PoolsideCommandError, PoolsideDevice
import pytest

from homeassistant.components.poolside.const import CONF_EXPOSE_POOL_DEVICES, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import TEST_CONTROLLER_UUID, FakePoolsideClient

from tests.common import MockConfigEntry

PUMP_UUID = "device-pump-1"
LIGHT_UUID = "device-light-1"
ACTUATOR_UUID = "device-actuator-1"
ACTUATOR_STATE_ENTITY_ID = "sensor.intake_valve_state"
ACTUATOR_POSITION_ENTITY_ID = "sensor.intake_valve_position"

MODE_ENTITY_ID = "sensor.test_residence_controller_mode"
POWER_ENTITY_ID = "sensor.pump_power"
POWER_STATE_ENTITY_ID = "sensor.pump_power_state"
WINTERIZED_ENTITY_ID = "sensor.pump_winterized"

# A pump descriptor exercising every DisplayProcessingLogic the integration
# renders, plus an unrecognized logic and one control-typed entry that must
# be skipped.
INFORMATION_FIELDS = json.dumps(
    [
        {
            "Name": "Watts",
            "DisplayName": "Power",
            "DisplayOrder": 1,
            "DisplayProcessingLogic": "WATTAGE",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "RPM",
            "DisplayName": "RPM",
            "DisplayOrder": 2,
            "DisplayProcessingLogic": "RPM",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "GPM",
            "DisplayName": "Flow",
            "DisplayOrder": 3,
            "DisplayProcessingLogic": "GPM",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "PSI",
            "DisplayName": "Pressure",
            "DisplayOrder": 4,
            "DisplayProcessingLogic": "PSI",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "PumpState",
            "DisplayName": "Status",
            "DisplayOrder": 5,
            "DisplayProcessingLogic": "LONG_STRING",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "CoolingDownUntil",
            "DisplayName": "Heater Cooldown Until",
            "DisplayOrder": 7,
            "DisplayProcessingLogic": "DATETIME",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "Vibration",
            "DisplayName": "Vibration",
            "DisplayOrder": 8,
            "DisplayProcessingLogic": "SPARKLINE",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "TargetSpeed",
            "DisplayName": "Target Speed",
            "DisplayOrder": 9,
            "DisplayProcessingLogic": "PERCENT",
            "FieldTypes": ["CONTROL"],
        },
        {
            "Name": "InletTemp",
            "DisplayName": "Inlet Temperature",
            "DisplayOrder": 10,
            "DisplayProcessingLogic": "TEMP_F",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "Output",
            "DisplayName": "Output Level",
            "DisplayOrder": 11,
            "DisplayProcessingLogic": "PERCENT",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "ChlorineRate",
            "DisplayName": "Chlorine Rate",
            "DisplayOrder": 12,
            "DisplayProcessingLogic": "MG_L",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "SaltPPM",
            "DisplayName": "Salt",
            "DisplayOrder": 13,
            "DisplayProcessingLogic": "PPM",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "Priming",
            "DisplayName": "Priming",
            "DisplayOrder": 14,
            "DisplayProcessingLogic": "ONOFF",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "FreezeProtection",
            "DisplayName": "Freeze Protection",
            "DisplayOrder": 15,
            "DisplayProcessingLogic": "BOOLEAN",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "TimeRemaining",
            "DisplayName": "Time Remaining",
            "DisplayOrder": 16,
            "DisplayProcessingLogic": "MS_TO_S",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "ErrorCount",
            "DisplayName": "Error Count",
            "DisplayOrder": 17,
            "DisplayProcessingLogic": "INTEGER",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "PowerFactor",
            "DisplayName": "Power Factor",
            "DisplayOrder": 18,
            "DisplayProcessingLogic": "FLOAT",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "SpeedMultiplier",
            "DisplayName": "Speed Multiplier",
            "DisplayOrder": 19,
            "DisplayProcessingLogic": "X",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "MotorCurrent",
            "DisplayName": "Motor Current",
            "DisplayOrder": 20,
            "DisplayProcessingLogic": "AMP",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "SensorCurrent",
            "DisplayName": "Sensor Current",
            "DisplayOrder": 21,
            "DisplayProcessingLogic": "UA",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "CellVoltage",
            "DisplayName": "Cell Voltage",
            "DisplayOrder": 22,
            "DisplayProcessingLogic": "MV",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "SupplyVoltage",
            "DisplayName": "Supply Voltage",
            "DisplayOrder": 23,
            "DisplayProcessingLogic": "VOLT",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "LightName",
            "DisplayName": "Show",
            "DisplayOrder": 24,
            "DisplayProcessingLogic": "LIGHT_NAME",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "Twinkle",
            "DisplayName": "Twinkle",
            "DisplayOrder": 25,
            "DisplayProcessingLogic": "TWINKLE",
            "FieldTypes": ["INFORMATION"],
        },
        {
            "Name": "TwinkleIncrements",
            "DisplayName": "Twinkle Increments",
            "DisplayOrder": 26,
            "FieldTypes": ["INFORMATION"],
        },
    ]
)

TWINKLE_ENTITY_ID = "sensor.pump_twinkle"

TWINKLE_INCREMENTS = json.dumps(
    [
        {"value": 0, "description": "Off"},
        {"value": 50, "description": "Half"},
        {"value": 100, "description": "Full"},
    ]
)


@pytest.fixture
def pool_devices() -> list[PoolsideDevice]:
    """One pump, as returned by Site.getPoolDevices."""
    return [PoolsideDevice(uuid=PUMP_UUID, name="Pump", device_type="Pump")]


async def setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry and settle."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_created_from_initial_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Each INFORMATION field becomes a sensor; control-typed fields and supporting states do not."""
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        POWER_ENTITY_ID,
        POWER_STATE_ENTITY_ID,
        WINTERIZED_ENTITY_ID,
        "sensor.pump_rpm",
        "sensor.pump_flow",
        "sensor.pump_pressure",
        "sensor.pump_status",
        "sensor.pump_heater_cooldown_until",
        "sensor.pump_vibration",
        "sensor.pump_inlet_temperature",
        "sensor.pump_output_level",
        "sensor.pump_chlorine_rate",
        "sensor.pump_salt",
        "sensor.pump_priming",
        "sensor.pump_freeze_protection",
        "sensor.pump_time_remaining",
        "sensor.pump_error_count",
        "sensor.pump_power_factor",
        "sensor.pump_speed_multiplier",
        "sensor.pump_motor_current",
        "sensor.pump_sensor_current",
        "sensor.pump_cell_voltage",
        "sensor.pump_supply_voltage",
        "sensor.pump_show",
        TWINKLE_ENTITY_ID,
    }


@pytest.mark.parametrize(
    ("field", "entity_id", "raw_value", "expected_state", "expected_unit"),
    [
        pytest.param("Watts", POWER_ENTITY_ID, "1250", "1250.0", "W", id="wattage"),
        pytest.param(
            "Watts", POWER_ENTITY_ID, "banana", STATE_UNKNOWN, "W", id="wattage-garbage"
        ),
        pytest.param("RPM", "sensor.pump_rpm", "2850", "2850.0", "rpm", id="rpm"),
        pytest.param("GPM", "sensor.pump_flow", "55", "55.0", "gal/min", id="gpm"),
        pytest.param("PSI", "sensor.pump_pressure", "12.4", "12.4", "psi", id="psi"),
        pytest.param(
            "PumpState",
            "sensor.pump_status",
            "PRIMING",
            "PRIMING",
            None,
            id="long-string",
        ),
        pytest.param(
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "2026-07-22T15:30:00+00:00",
            "2026-07-22T15:30:00+00:00",
            None,
            id="datetime",
        ),
        pytest.param(
            # The test harness's local timezone is US/Pacific (UTC-7 in July).
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "2026-07-22T15:30:00",
            "2026-07-22T22:30:00+00:00",
            None,
            id="datetime-naive-assumed-local",
        ),
        pytest.param(
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            "not-a-date",
            STATE_UNKNOWN,
            None,
            id="datetime-garbage",
        ),
        pytest.param(
            "Vibration",
            "sensor.pump_vibration",
            "42",
            "42",
            None,
            id="unrecognized-logic-renders-as-text",
        ),
        pytest.param(
            "CoolingDownUntil",
            "sensor.pump_heater_cooldown_until",
            '"2026-07-22T15:30:00+00:00"',
            "2026-07-22T15:30:00+00:00",
            None,
            id="datetime-double-json-encoded",
        ),
        pytest.param(
            "InletTemp",
            "sensor.pump_inlet_temperature",
            "78",
            "78.0",
            UnitOfTemperature.FAHRENHEIT,
            id="temp-f",
        ),
        pytest.param(
            "Output", "sensor.pump_output_level", "85", "85.0", "%", id="percent"
        ),
        pytest.param(
            "ChlorineRate",
            "sensor.pump_chlorine_rate",
            "1.25",
            "1.25",
            "mg/L",
            id="mg-l",
        ),
        pytest.param("SaltPPM", "sensor.pump_salt", "3100", "3100.0", "ppm", id="ppm"),
        pytest.param("Priming", "sensor.pump_priming", "ON", "on", None, id="onoff-on"),
        pytest.param(
            "Priming", "sensor.pump_priming", "OFF", "off", None, id="onoff-off"
        ),
        pytest.param(
            "Priming",
            "sensor.pump_priming",
            "UNKNOWN",
            STATE_UNKNOWN,
            None,
            id="onoff-unknown-sentinel",
        ),
        pytest.param(
            "Priming", "sensor.pump_priming", True, "on", None, id="onoff-boolean"
        ),
        pytest.param(
            "FreezeProtection",
            "sensor.pump_freeze_protection",
            "true",
            "yes",
            None,
            id="boolean-true",
        ),
        pytest.param(
            "FreezeProtection",
            "sensor.pump_freeze_protection",
            False,
            "no",
            None,
            id="boolean-false",
        ),
        pytest.param(
            "TimeRemaining",
            "sensor.pump_time_remaining",
            "9500",
            "9.5",
            "s",
            id="ms-converted-to-seconds",
        ),
        pytest.param(
            "ErrorCount", "sensor.pump_error_count", "3", "3.0", None, id="integer"
        ),
        pytest.param(
            "PowerFactor", "sensor.pump_power_factor", "0.92", "0.92", None, id="float"
        ),
        pytest.param(
            "SpeedMultiplier",
            "sensor.pump_speed_multiplier",
            "2",
            "2.0",
            "x",
            id="multiplier",
        ),
        pytest.param(
            "MotorCurrent", "sensor.pump_motor_current", "4.2", "4.2", "A", id="amp"
        ),
        pytest.param(
            "SensorCurrent",
            "sensor.pump_sensor_current",
            "150",
            "150.0",
            UnitOfElectricCurrent.MICROAMPERE,
            id="microamp",
        ),
        pytest.param(
            "CellVoltage",
            "sensor.pump_cell_voltage",
            "450",
            "450.0",
            "mV",
            id="millivolt",
        ),
        pytest.param(
            "SupplyVoltage",
            "sensor.pump_supply_voltage",
            "240",
            "240.0",
            "V",
            id="volt",
        ),
        pytest.param(
            "LightName",
            "sensor.pump_show",
            "Party Mode",
            "Party Mode",
            None,
            id="light-name-plain-string",
        ),
    ],
)
async def test_field_value_rendering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    field: str,
    entity_id: str,
    raw_value: Any,
    expected_state: str,
    expected_unit: str | None,
) -> None:
    """Values render per the field's DisplayProcessingLogic, with the right unit.

    Uses imperial units so the psi native unit matches the test hass's unit
    system and needs no conversion.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    mock_poolside_client.set_status(PUMP_UUID, field, raw_value)
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


@pytest.mark.parametrize(
    ("increments", "raw_value", "expected_state"),
    [
        pytest.param(TWINKLE_INCREMENTS, "50", "Half", id="matched"),
        pytest.param(TWINKLE_INCREMENTS, 100, "Full", id="matched-numeric"),
        pytest.param(TWINKLE_INCREMENTS, "50.0", "Half", id="matched-float-notation"),
        pytest.param(TWINKLE_INCREMENTS, "75", "75", id="unlisted-value-stays-raw"),
        pytest.param(None, "50", "50", id="missing-document-stays-raw"),
        pytest.param("not json", "50", "50", id="unparsable-document-stays-raw"),
    ],
)
async def test_twinkle_sensor_translates_increments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    increments: str | None,
    raw_value: Any,
    expected_state: str,
) -> None:
    """Twinkle renders as its TwinkleIncrements description, raw when unresolvable."""
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    mock_poolside_client.set_status(PUMP_UUID, "TwinkleIncrements", increments)
    mock_poolside_client.set_status(PUMP_UUID, "Twinkle", raw_value)
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(TWINKLE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("setup_integration")
async def test_sensors_added_when_information_fields_arrive_later(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A device with no snapshot grows its sensors when the descriptor is pushed."""
    assert hass.states.get(POWER_ENTITY_ID) is None

    fake_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(PUMP_UUID, "Watts", "900")
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "900.0"


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param("ON", "on", id="on"),
        pytest.param("OFF", "off", id="off"),
        pytest.param("UNKNOWN", STATE_UNKNOWN, id="unknown-sentinel"),
        pytest.param(True, "on", id="boolean"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_actual_power_state_sensor(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    raw_value: Any,
    expected_state: str,
) -> None:
    """Every pool device reports ActualPowerState, present from setup.

    The sensor exists before any telemetry (or the InformationFields
    descriptor) arrives, and renders ON/OFF pushes; the UNKNOWN sentinel
    means the hardware can't confirm, not a real state.
    """
    state = hass.states.get(POWER_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(PUMP_UUID, "ActualPowerState", raw_value)
    await hass.async_block_till_done()

    state = hass.states.get(POWER_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_descriptor_dedicated_fields_not_duplicated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A descriptor listing ActualPowerState or Winterized doesn't clash with the dedicated sensors."""
    fields = json.dumps(
        [
            {
                "Name": "ActualPowerState",
                "DisplayName": "Power State",
                "DisplayOrder": 1,
                "DisplayProcessingLogic": "ONOFF",
                "FieldTypes": ["INFORMATION"],
            },
            {
                "Name": "Winterized",
                "DisplayName": "Winterized",
                "DisplayOrder": 2,
                "DisplayProcessingLogic": "BOOLEAN",
                "FieldTypes": ["INFORMATION"],
            },
        ]
    )
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", fields)
    mock_poolside_client.set_status(PUMP_UUID, "ActualPowerState", "ON")
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        POWER_STATE_ENTITY_ID,
        WINTERIZED_ENTITY_ID,
    }
    state = hass.states.get(POWER_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(True, "true", id="boolean-true"),
        pytest.param(False, "false", id="boolean-false"),
        pytest.param("true", "true", id="string-true"),
        pytest.param("false", "false", id="string-false"),
        pytest.param("garbage", STATE_UNKNOWN, id="unrecognized"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_winterized_sensor(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
    raw_value: Any,
    expected_state: str,
) -> None:
    """Every pool device gets a winterized sensor, present from setup.

    The sensor exists before any telemetry (or the InformationFields
    descriptor) arrives and renders the pushed Winterized flag as
    true/false.
    """
    state = hass.states.get(WINTERIZED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(PUMP_UUID, "Winterized", raw_value)
    await hass.async_block_till_done()

    state = hass.states.get(WINTERIZED_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    "device_type",
    [
        pytest.param("Light", id="mixed-case"),
        pytest.param("LIGHT", id="upper-case"),
    ],
)
async def test_light_device_sensors_synthesized_without_descriptor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_type: str,
) -> None:
    """Light devices get their fixed field set from setup; no InformationFields needed."""
    mock_poolside_client.async_get_pool_devices.return_value = [
        PoolsideDevice(uuid=LIGHT_UUID, name="Spa Light", device_type=device_type)
    ]
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        "sensor.spa_light_power_state",
        "sensor.spa_light_winterized",
        "sensor.spa_light_power",
        "sensor.spa_light_show",
        "sensor.spa_light_brightness",
        "sensor.spa_light_speed",
        "sensor.spa_light_twinkle",
    }


@pytest.mark.parametrize(
    ("field", "entity_id", "raw_value", "expected_state", "expected_unit"),
    [
        pytest.param(
            "PowerState", "sensor.spa_light_power", "ON", "on", None, id="power-onoff"
        ),
        pytest.param(
            "LightName",
            "sensor.spa_light_show",
            "Caribbean Blue",
            "Caribbean Blue",
            None,
            id="light-name-plain-string",
        ),
        pytest.param(
            "Brightness",
            "sensor.spa_light_brightness",
            "80",
            "80.0",
            "%",
            id="brightness-percent",
        ),
        pytest.param(
            "Speed", "sensor.spa_light_speed", "2", "2.0", "x", id="speed-multiplier"
        ),
    ],
)
async def test_light_device_field_rendering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    field: str,
    entity_id: str,
    raw_value: str,
    expected_state: str,
    expected_unit: str | None,
) -> None:
    """Each fixed light field renders per its assigned processing logic."""
    mock_poolside_client.async_get_pool_devices.return_value = [
        PoolsideDevice(uuid=LIGHT_UUID, name="Spa Light", device_type="Light")
    ]
    mock_poolside_client.set_status(LIGHT_UUID, field, raw_value)
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit


async def test_light_device_twinkle_translates_increments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A light's Twinkle resolves through TwinkleIncrements like any TWINKLE field."""
    mock_poolside_client.async_get_pool_devices.return_value = [
        PoolsideDevice(uuid=LIGHT_UUID, name="Spa Light", device_type="Light")
    ]
    mock_poolside_client.set_status(LIGHT_UUID, "TwinkleIncrements", TWINKLE_INCREMENTS)
    mock_poolside_client.set_status(LIGHT_UUID, "Twinkle", "100")
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get("sensor.spa_light_twinkle")
    assert state is not None
    assert state.state == "Full"


def _actuator_device(device_type: str = "ActuatorTwoWay") -> PoolsideDevice:
    return PoolsideDevice(
        uuid=ACTUATOR_UUID, name="Intake Valve", device_type=device_type
    )


@pytest.mark.parametrize(
    "device_type",
    [
        pytest.param("ActuatorTwoWay", id="two-way"),
        pytest.param("ActuatorThreeWay", id="three-way"),
        pytest.param("ACTUATOR_TWO_WAY", id="upper-case"),
    ],
)
async def test_actuator_sensors_synthesized_without_descriptor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_type: str,
) -> None:
    """Actuators get state, position, and fallback calibration sensors - and no power state."""
    mock_poolside_client.async_get_pool_devices.return_value = [
        _actuator_device(device_type)
    ]
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        "sensor.intake_valve_winterized",
        ACTUATOR_STATE_ENTITY_ID,
        ACTUATOR_POSITION_ENTITY_ID,
        "sensor.intake_valve_calibration_left_to_right",
        "sensor.intake_valve_calibration_right_to_left",
    }


async def test_actuator_published_descriptor_replaces_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A published InformationFields document takes the fallback list's place."""
    fields = json.dumps(
        [
            {
                "Name": "MotorCurrent",
                "DisplayName": "Motor Current",
                "DisplayOrder": 1,
                "DisplayProcessingLogic": "AMP",
                "FieldTypes": ["INFORMATION"],
            }
        ]
    )
    mock_poolside_client.async_get_pool_devices.return_value = [_actuator_device()]
    mock_poolside_client.set_status(ACTUATOR_UUID, "InformationFields", fields)
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        "sensor.intake_valve_winterized",
        ACTUATOR_STATE_ENTITY_ID,
        ACTUATOR_POSITION_ENTITY_ID,
        "sensor.intake_valve_motor_current",
    }


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param("IDLE", "idle", id="idle"),
        pytest.param("WAITING_TO_MOVE", "waiting_to_move", id="waiting"),
        pytest.param("ATTEMPTING_TO_MOVE", "attempting_to_move", id="moving"),
        pytest.param("CALIBRATING", "calibrating", id="calibrating"),
        pytest.param("OVERLOAD", "overload", id="overload"),
        pytest.param("ERROR", "error", id="error"),
        pytest.param("FAILED", "failed", id="failed"),
        pytest.param("OFFLINE", "offline", id="offline"),
        pytest.param("MAGMA", STATE_UNKNOWN, id="unrecognized"),
    ],
)
async def test_actuator_state_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    raw_value: str,
    expected_state: str,
) -> None:
    """FriendlyState renders as its enum option; unrecognized values as unknown."""
    mock_poolside_client.async_get_pool_devices.return_value = [_actuator_device()]
    mock_poolside_client.set_status(ACTUATOR_UUID, "FriendlyState", raw_value)
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(ACTUATOR_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param("40", "40.0", id="in-range"),
        pytest.param(0, "0.0", id="lower-bound"),
        pytest.param("100", "100.0", id="upper-bound"),
        pytest.param("255", STATE_UNKNOWN, id="out-of-range-sentinel"),
        pytest.param("-5", STATE_UNKNOWN, id="negative"),
        pytest.param("banana", STATE_UNKNOWN, id="garbage"),
    ],
)
async def test_actuator_position_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    raw_value: Any,
    expected_state: str,
) -> None:
    """ActualPositionPercentLeft renders as a percentage; out-of-range means no data."""
    mock_poolside_client.async_get_pool_devices.return_value = [_actuator_device()]
    mock_poolside_client.set_status(
        ACTUATOR_UUID, "ActualPositionPercentLeft", raw_value
    )
    await setup_entry(hass, mock_config_entry)

    state = hass.states.get(ACTUATOR_POSITION_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "%"


async def test_pool_device_registered_under_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The pool device exists even before any telemetry, linked via the controller."""
    await setup_entry(hass, mock_config_entry)

    controller = device_registry.async_get_device({(DOMAIN, TEST_CONTROLLER_UUID)})
    assert controller is not None
    device = device_registry.async_get_device({(DOMAIN, PUMP_UUID)})
    assert device is not None
    assert device.via_device_id == controller.id
    assert device.manufacturer == "Poolside"
    assert device.model == "Pump"
    assert device.name == "Pump"


async def test_pool_device_named_from_the_device_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The device is named from the getPoolDevices Name, not its DeviceType."""
    mock_poolside_client.async_get_pool_devices.return_value = [
        PoolsideDevice(uuid=PUMP_UUID, name="Main Pump", device_type="Pump")
    ]
    await setup_entry(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, PUMP_UUID)})
    assert device is not None
    assert device.name == "Main Pump"
    assert device.model == "Pump"


async def test_disabling_pool_devices_option_removes_them(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Turning the option off skips the fetch and prunes existing pool devices."""
    await setup_entry(hass, mock_config_entry)
    assert device_registry.async_get_device({(DOMAIN, PUMP_UUID)}) is not None
    assert hass.states.get(POWER_STATE_ENTITY_ID) is not None

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_EXPOSE_POOL_DEVICES: False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert mock_config_entry.options == {CONF_EXPOSE_POOL_DEVICES: False}
    assert device_registry.async_get_device({(DOMAIN, PUMP_UUID)}) is None
    assert hass.states.get(POWER_STATE_ENTITY_ID) is None
    mock_poolside_client.async_get_pool_devices.assert_awaited_once()


async def test_setup_succeeds_without_pool_device_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Firmware without Site.getPoolDevices loads normally with no pool devices."""
    mock_poolside_client.async_get_pool_devices.side_effect = PoolsideCommandError(
        "unknown method"
    )
    await setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.pool_devices == []
