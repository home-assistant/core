"""Tests for pool device sub-devices and their InformationFields sensors."""

import json
from typing import Any

import pytest

from homeassistant.components.poolside.client import PoolsideCommandError
from homeassistant.components.poolside.const import DOMAIN
from homeassistant.components.poolside.models import PoolsideDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import TEST_CONTROLLER_UUID, FakePoolsideClient

from tests.common import MockConfigEntry

PUMP_UUID = "device-pump-1"

MODE_ENTITY_ID = "sensor.test_residence_controller_mode"
POWER_ENTITY_ID = "sensor.pump_power"
POWER_STATE_ENTITY_ID = "sensor.pump_power_state"

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
    """Each INFORMATION field becomes a sensor; control-typed fields do not."""
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", INFORMATION_FIELDS)
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        POWER_ENTITY_ID,
        POWER_STATE_ENTITY_ID,
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


async def test_descriptor_actual_power_state_not_duplicated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A descriptor that lists ActualPowerState doesn't clash with the dedicated sensor."""
    fields = json.dumps(
        [
            {
                "Name": "ActualPowerState",
                "DisplayName": "Power State",
                "DisplayOrder": 1,
                "DisplayProcessingLogic": "ONOFF",
                "FieldTypes": ["INFORMATION"],
            }
        ]
    )
    mock_poolside_client.set_status(PUMP_UUID, "InformationFields", fields)
    mock_poolside_client.set_status(PUMP_UUID, "ActualPowerState", "ON")
    await setup_entry(hass, mock_config_entry)

    assert set(hass.states.async_entity_ids("sensor")) == {
        MODE_ENTITY_ID,
        POWER_STATE_ENTITY_ID,
    }
    state = hass.states.get(POWER_STATE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


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
