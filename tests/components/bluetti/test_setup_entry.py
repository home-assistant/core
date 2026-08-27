"""Tests for the sensor platform's async_setup_entry()."""

from enum import Enum
from unittest.mock import MagicMock

from bluetti_modbus_lib.modbus.client import ClientReturnValue

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.components.bluetti.sensor import (
    BluettiEnergySensor,
    BluettiEstimatedBatteryPowerSensor,
    BluettiModbusSensor,
    BluettiSensor,
    async_setup_entry as sensor_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

from tests.common import MockConfigEntry


def _entry_with_devices(hass, devices: list[BluettiDevice], modbus_coordinators=None) -> MockConfigEntry:
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
        modbus_coordinators=modbus_coordinators or {},
    )
    return entry


async def test_sensor_setup_entry_creates_expected_entities(hass):
    """Sensor setup entry creates expected entities."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
            {
                "fnCode": "InvWorkState", "fnName": "Inverter", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.ENUM", "unit": None},
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "Weird", "fnName": "Weird sensor", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.UNKNOWN", "unit": None},
            },
            {"fnCode": "onLine", "fnName": "Online", "fnValue": "1", "fnType": "SENSOR"},
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
    assert enum_sensor.native_value == "Grid"  # exercises the support_mode_values branch


async def test_sensor_setup_entry_survives_sensor_info_missing_unit_key(hass):
    """Sensor setup entry survives sensor info missing unit key."""
    # Regression test for #101/#102: real API responses can omit the "unit"
    # key entirely from sensorInfo (not just set it to None) for types like
    # ENUM. A plain state.sensor_info["unit"] KeyError there used to abort
    # the whole setup loop, silently dropping every not-yet-processed
    # sensor on every device - not just the one with the missing key.
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="EL400",
        state_list=[
            {
                "fnCode": "InvWorkState", "fnName": "Inverter", "fnValue": "1", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.ENUM"},  # no "unit" key at all
                "supportModeValues": [{"code": "1", "name": "Grid"}],
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "100", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    sensors = [e for e in added if isinstance(e, BluettiSensor)]
    assert {s._state_obj.fn_code for s in sensors} == {"InvWorkState", "GridAllTotalPower"}


async def test_sensor_setup_entry_creates_energy_sensor_for_power_sensors(hass):
    """Sensor setup entry creates energy sensor for power sensors."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "100", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
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


async def test_sensor_setup_entry_creates_estimated_battery_power_sensors(hass):
    """Sensor setup entry creates estimated battery power sensors."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "PVAllTotalPower", "fnName": "PV Input Power", "fnValue": "500", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "GridAllTotalPower", "fnName": "Grid Input Power", "fnValue": "0", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
            {
                "fnCode": "ACLoadAllTotalPower", "fnName": "AC Load Power", "fnValue": "200", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.POWER", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    estimated = [e for e in added if isinstance(e, BluettiEstimatedBatteryPowerSensor)]
    assert len(estimated) == 2
    charge = next(e for e in estimated if e.unique_id == "SN1_EstimatedBatteryChargePower")
    discharge = next(e for e in estimated if e.unique_id == "SN1_EstimatedBatteryDischargePower")
    # 500 W PV - 200 W AC load = 300 W surplus available to charge.
    assert charge.native_value == 300.0
    assert discharge.native_value == 0.0

    energy_companion_ids = {
        "SN1_EstimatedBatteryChargePower_energy",
        "SN1_EstimatedBatteryDischargePower_energy",
    }
    energy_companions = [
        e for e in added if isinstance(e, BluettiEnergySensor) and e.unique_id in energy_companion_ids
    ]
    assert len(energy_companions) == 2


async def test_sensor_setup_entry_skips_estimated_battery_sensors_when_data_missing(hass):
    """Sensor setup entry skips estimated battery sensors when data missing."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    entry = _entry_with_devices(hass, [device])
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    assert not any(isinstance(e, BluettiEstimatedBatteryPowerSensor) for e in added)


async def test_sensor_setup_entry_with_no_matching_states_adds_nothing(hass):
    """Sensor setup entry with no matching states adds nothing."""
    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L",
        state_list=[{"fnCode": "SetCtrlAc", "fnName": "AC", "fnValue": "0", "fnType": "SWITCH"}],
    )
    entry = _entry_with_devices(hass, [device])
    async_add_entities = MagicMock()

    result = await sensor_setup_entry(hass, entry, async_add_entities)

    assert result is True
    async_add_entities.assert_not_called()


async def test_sensor_setup_entry_creates_modbus_sensors_grouped_with_cloud_device(hass):
    """Sensor setup entry creates modbus sensors grouped with cloud device."""

    class _FakeInverterStatus(Enum):
        STANDBY = 0

    device = BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260",
        state_list=[
            {
                "fnCode": "SOC", "fnName": "Battery", "fnValue": "50", "fnType": "SENSOR",
                "sensorInfo": {"sensorType": "SensorDeviceClass.BATTERY", "unit": None},
            },
        ],
    )
    # device_class/state_class/entity_category are no longer carried on
    # ClientReturnValue (bluetti_modbus_lib doesn't know about HA entity
    # concepts) - BluettiModbusSensor looks them up in
    # modbus_field_metadata.MODBUS_FIELD_METADATA by field name instead, so
    # these real field names exercise that lookup, not a mocked value.
    fields = {
        # Excluded - duplicates the cloud SOC sensor already added above.
        "b_soc": ClientReturnValue(name="b_soc", unit="%", value=42),
        "b_cycle_count": ClientReturnValue(name="b_cycle_count", unit=None, value=12),
        # CONFIG must be remapped to DIAGNOSTIC - SensorEntity forbids CONFIG.
        "b_soc_high": ClientReturnValue(name="b_soc_high", unit="%", value=100),
        "d_inverter_status": ClientReturnValue(
            name="d_inverter_status", unit=None, value=_FakeInverterStatus.STANDBY
        ),
        "g_i_f": ClientReturnValue(name="g_i_f", unit="Hz", value=50.0),
    }
    modbus_coordinator = MagicMock(data=fields)
    # Entities are created from the device's declared fields (see sensor.py),
    # not from modbus_coordinator.data directly - independent of whether the
    # coordinator has completed a poll yet.
    modbus_coordinator.device.field_names.return_value = list(fields.keys())

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    modbus_sensors = {s._field_name: s for s in added if isinstance(s, BluettiModbusSensor)}
    assert set(modbus_sensors) == {"b_cycle_count", "b_soc_high", "d_inverter_status", "g_i_f"}

    cloud_sensor = next(e for e in added if isinstance(e, BluettiSensor))
    assert modbus_sensors["b_cycle_count"].device_info["identifiers"] == cloud_sensor.device_info["identifiers"]

    assert modbus_sensors["g_i_f"].device_class == SensorDeviceClass.FREQUENCY
    assert modbus_sensors["g_i_f"].state_class == SensorStateClass.MEASUREMENT

    assert modbus_sensors["b_soc_high"].entity_category == EntityCategory.DIAGNOSTIC
    assert modbus_sensors["b_cycle_count"].native_value == 12
    assert modbus_sensors["d_inverter_status"].native_value == "STANDBY"

    modbus_coordinator.data = {}
    assert modbus_sensors["b_cycle_count"].native_value is None


async def test_modbus_sensors_are_created_even_when_the_first_poll_hasnt_completed(hass):
    """Modbus sensors are created even when the first poll hasn't completed.

    Regression test: local Modbus is optional/supplementary, so a failed or
    still-pending first refresh must not prevent entities from ever being
    created - entities must come from the device's declared fields, not
    from whatever the coordinator happened to have read by the time setup
    runs once.
    """
    device = BluettiDevice(device_id="SN1", on_line="1", name="Test", sn="SN1", model="Balco260")
    modbus_coordinator = MagicMock(data=None)
    modbus_coordinator.device.field_names.return_value = ["b_soc_high"]

    entry = _entry_with_devices(hass, [device], modbus_coordinators={"SN1": modbus_coordinator})
    added = []

    await sensor_setup_entry(hass, entry, added.extend)

    modbus_sensors = [s for s in added if isinstance(s, BluettiModbusSensor)]
    assert len(modbus_sensors) == 1
    assert modbus_sensors[0].native_value is None
    assert modbus_sensors[0].native_unit_of_measurement is None

    # Once the coordinator's next poll actually succeeds, the same
    # already-created entity picks up the real value and unit.
    modbus_coordinator.data = {"b_soc_high": ClientReturnValue(name="b_soc_high", unit="%", value=100)}
    assert modbus_sensors[0].native_value == 100
    assert modbus_sensors[0].native_unit_of_measurement == "%"


async def test_sensor_setup_entry_skips_modbus_coordinator_for_unknown_device(hass):
    """Sensor setup entry skips modbus coordinator for unknown device."""
    entry = _entry_with_devices(hass, [], modbus_coordinators={"UNKNOWN_SN": MagicMock(data={})})
    added = []

    result = await sensor_setup_entry(hass, entry, added.extend)

    assert result is True
    assert added == []


