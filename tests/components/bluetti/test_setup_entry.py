"""Tests for the sensor platform's async_setup_entry()."""

from unittest.mock import MagicMock

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.components.bluetti.sensor import (
    BluettiEnergySensor,
    BluettiEstimatedBatteryPowerSensor,
    BluettiSensor,
    async_setup_entry as sensor_setup_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _entry_with_devices(
    hass: HomeAssistant, devices: list[BluettiDevice]
) -> MockConfigEntry:
    for device in devices:
        device.coordinator = MagicMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    bluetti_data = BluettiData.__new__(BluettiData)
    bluetti_data.devices = devices
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=bluetti_data,
        stomp_client=MagicMock(),
        coordinators={},
    )
    return entry


async def test_sensor_setup_entry_creates_expected_entities(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry creates expected entities."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SOC",
                "fnName": "Battery",
                "fnValue": "50",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            {
                "fnCode": "InvWorkState",
                "fnName": "Inverter",
                "fnValue": "1",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.ENUM", "unit": None},
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "Weird",
                "fnName": "Weird sensor",
                "fnValue": "1",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.UNKNOWN", "unit": None},
            },
            {
                "fnCode": "onLine",
                "fnName": "Online",
                "fnValue": "1",
                "fnType": "SENSOR",
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    # SOC + InvWorkState sensors; onLine is a binary_sensor entity, out of
    # scope for the sensor-only platform this PR adds.
    assert len(added) == 2
    sensors = [e for e in added if isinstance(e, BluettiSensor)]
    assert len(sensors) == 2

    enum_sensor = next(s for s in sensors if s._state_obj.fn_code == "InvWorkState")
    assert (
        enum_sensor.native_value == "Grid"
    )  # exercises the support_mode_values branch


async def test_sensor_setup_entry_survives_sensor_info_missing_unit_key(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry survives sensor info missing unit key."""
    # Regression test for #101/#102: real API responses can omit the "unit"
    # key entirely from sensorInfo (not just set it to None) for types like
    # ENUM. A plain state.sensor_info["unit"] KeyError there used to abort
    # the whole setup loop, silently dropping every not-yet-processed
    # sensor on every device - not just the one with the missing key.
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="EL400",
        state_list=[
            {
                "fnCode": "InvWorkState",
                "fnName": "Inverter",
                "fnValue": "1",
                "fnType": "SENSOR",
                "sensorInfo": {
                    "sensorType": "SensorDeviceClass.ENUM"
                },  # no "unit" key at all
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "GridAllTotalPower",
                "fnName": "Grid Input Power",
                "fnValue": "100",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    sensors = [e for e in added if isinstance(e, BluettiSensor)]
    assert {s._state_obj.fn_code for s in sensors} == {
        "InvWorkState",
        "GridAllTotalPower",
    }


async def test_sensor_setup_entry_creates_energy_sensor_for_power_sensors(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry creates energy sensor for power sensors."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower",
                "fnName": "PV Input Power",
                "fnValue": "100",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "SOC",
                "fnName": "Battery",
                "fnValue": "50",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    # Power sensor + its energy companion + the plain (non-power) battery sensor.
    assert len(added) == 3
    energy_sensors = [e for e in added if isinstance(e, BluettiEnergySensor)]
    assert len(energy_sensors) == 1
    assert energy_sensors[0].unique_id == "SN1_PVAllTotalPower_energy"
    assert energy_sensors[0].native_unit_of_measurement == "kWh"


async def test_sensor_setup_entry_creates_estimated_battery_power_sensors(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry creates estimated battery power sensors."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower",
                "fnName": "PV Input Power",
                "fnValue": "500",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "GridAllTotalPower",
                "fnName": "Grid Input Power",
                "fnValue": "0",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "ACLoadAllTotalPower",
                "fnName": "AC Load Power",
                "fnValue": "200",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    estimated = [e for e in added if isinstance(e, BluettiEstimatedBatteryPowerSensor)]
    assert len(estimated) == 2
    charge = next(
        e for e in estimated if e.unique_id == "SN1_EstimatedBatteryChargePower"
    )
    discharge = next(
        e for e in estimated if e.unique_id == "SN1_EstimatedBatteryDischargePower"
    )
    # 500 W PV - 200 W AC load = 300 W surplus available to charge.
    assert charge.native_value == 300.0
    assert discharge.native_value == 0.0

    energy_companion_ids = {
        "SN1_EstimatedBatteryChargePower_energy",
        "SN1_EstimatedBatteryDischargePower_energy",
    }
    energy_companions = [
        e
        for e in added
        if isinstance(e, BluettiEnergySensor) and e.unique_id in energy_companion_ids
    ]
    assert len(energy_companions) == 2


async def test_sensor_setup_entry_skips_estimated_battery_sensors_when_data_missing(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry skips estimated battery sensors when data missing."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SOC",
                "fnName": "Battery",
                "fnValue": "50",
                "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert not any(isinstance(e, BluettiEstimatedBatteryPowerSensor) for e in added)


async def test_sensor_setup_entry_with_no_matching_states_adds_nothing(
    hass: HomeAssistant,
) -> None:
    """Sensor setup entry with no matching states adds nothing."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}
        ],
    )
    entry = _entry_with_devices(hass, [device])
    async_add_entities = MagicMock()

    await sensor_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_not_called()
