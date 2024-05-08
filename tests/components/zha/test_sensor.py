"""Test ZHA sensor."""

from datetime import timedelta
import math
from unittest.mock import MagicMock, patch

import pytest
import zigpy.profiles.zha
from zigpy.quirks import CustomCluster
from zigpy.quirks.v2 import CustomDeviceV2, add_to_registry_v2
from zigpy.quirks.v2.homeassistant import UnitOfMass
import zigpy.types as t
from zigpy.zcl.clusters import general, homeautomation, hvac, measurement, smartenergy
from zigpy.zcl.clusters.hvac import Thermostat
from zigpy.zcl.clusters.manufacturer_specific import ManufacturerSpecificCluster

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.zha.core import ZHADevice
from homeassistant.components.zha.core.const import ZHA_CLUSTER_HANDLER_READS_PER_REQ
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, restore_state
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    find_entity_ids,
    send_attribute_report,
    send_attributes_report,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_load_restore_state_from_storage,
)

ENTITY_ID_PREFIX = "sensor.fakemanufacturer_fakemodel_{}"


@pytest.fixture(autouse=True)
def sensor_platform_only():
    """Only set up the sensor and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.SENSOR,
        ),
    ):
        yield


@pytest.fixture
async def elec_measurement_zigpy_dev(hass: HomeAssistant, zigpy_device_mock):
    """Electric Measurement zigpy device."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    homeautomation.ElectricalMeasurement.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.SIMPLE_SENSOR,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        },
    )
    zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100
    zigpy_device.endpoints[1].electrical_measurement.PLUGGED_ATTR_READS = {
        "ac_current_divisor": 10,
        "ac_current_multiplier": 1,
        "ac_power_divisor": 10,
        "ac_power_multiplier": 1,
        "ac_voltage_divisor": 10,
        "ac_voltage_multiplier": 1,
        "measurement_type": 8,
        "power_divisor": 10,
        "power_multiplier": 1,
    }
    return zigpy_device


@pytest.fixture
async def elec_measurement_zha_dev(elec_measurement_zigpy_dev, zha_device_joined):
    """Electric Measurement ZHA device."""

    zha_dev = await zha_device_joined(elec_measurement_zigpy_dev)
    zha_dev.available = True
    return zha_dev


async def async_test_humidity(hass: HomeAssistant, cluster, entity_id):
    """Test humidity sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 100})
    assert_state(hass, entity_id, "10.0", PERCENTAGE)


async def async_test_temperature(hass: HomeAssistant, cluster, entity_id):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 2900, 2: 100})
    assert_state(hass, entity_id, "29.0", UnitOfTemperature.CELSIUS)


async def async_test_pressure(hass: HomeAssistant, cluster, entity_id):
    """Test pressure sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 10000})
    assert_state(hass, entity_id, "1000", UnitOfPressure.HPA)

    await send_attributes_report(hass, cluster, {0: 1000, 20: -1, 16: 10000})
    assert_state(hass, entity_id, "1000", UnitOfPressure.HPA)


async def async_test_illuminance(hass: HomeAssistant, cluster, entity_id):
    """Test illuminance sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 10, 2: 20})
    assert_state(hass, entity_id, "1", LIGHT_LUX)

    await send_attributes_report(hass, cluster, {1: 0, 0: 0, 2: 20})
    assert_state(hass, entity_id, "0", LIGHT_LUX)

    await send_attributes_report(hass, cluster, {1: 0, 0: 0xFFFF, 2: 20})
    assert_state(hass, entity_id, "unknown", LIGHT_LUX)


async def async_test_metering(hass: HomeAssistant, cluster, entity_id):
    """Test Smart Energy metering sensor."""
    await send_attributes_report(hass, cluster, {1025: 1, 1024: 12345, 1026: 100})
    assert_state(hass, entity_id, "12345.0", None)
    assert hass.states.get(entity_id).attributes["status"] == "NO_ALARMS"
    assert hass.states.get(entity_id).attributes["device_type"] == "Electric Metering"

    await send_attributes_report(hass, cluster, {1024: 12346, "status": 64 + 8})
    assert_state(hass, entity_id, "12346.0", None)
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|POWER_FAILURE",
        "POWER_FAILURE|SERVICE_DISCONNECT",
    )

    await send_attributes_report(
        hass, cluster, {"status": 64 + 8, "metering_device_type": 1}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|NOT_DEFINED",
        "NOT_DEFINED|SERVICE_DISCONNECT",
    )

    await send_attributes_report(
        hass, cluster, {"status": 64 + 8, "metering_device_type": 2}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|PIPE_EMPTY",
        "PIPE_EMPTY|SERVICE_DISCONNECT",
    )

    await send_attributes_report(
        hass, cluster, {"status": 64 + 8, "metering_device_type": 5}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|TEMPERATURE_SENSOR",
        "TEMPERATURE_SENSOR|SERVICE_DISCONNECT",
    )

    # Status for other meter types
    await send_attributes_report(
        hass, cluster, {"status": 32, "metering_device_type": 4}
    )
    assert hass.states.get(entity_id).attributes["status"] in ("<bitmap8.32: 32>", "32")


async def async_test_smart_energy_summation_delivered(
    hass: HomeAssistant, cluster, entity_id
):
    """Test SmartEnergy Summation delivered sensor."""

    await send_attributes_report(
        hass, cluster, {1025: 1, "current_summ_delivered": 12321, 1026: 100}
    )
    assert_state(hass, entity_id, "12.321", UnitOfEnergy.KILO_WATT_HOUR)
    assert hass.states.get(entity_id).attributes["status"] == "NO_ALARMS"
    assert hass.states.get(entity_id).attributes["device_type"] == "Electric Metering"
    assert (
        hass.states.get(entity_id).attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.ENERGY
    )


async def async_test_smart_energy_summation_received(
    hass: HomeAssistant, cluster, entity_id
):
    """Test SmartEnergy Summation received sensor."""

    await send_attributes_report(
        hass, cluster, {1025: 1, "current_summ_received": 12321, 1026: 100}
    )
    assert_state(hass, entity_id, "12.321", UnitOfEnergy.KILO_WATT_HOUR)
    assert hass.states.get(entity_id).attributes["status"] == "NO_ALARMS"
    assert hass.states.get(entity_id).attributes["device_type"] == "Electric Metering"
    assert (
        hass.states.get(entity_id).attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.ENERGY
    )


async def async_test_electrical_measurement(hass: HomeAssistant, cluster, entity_id):
    """Test electrical measurement sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 1291: 100, 10: 1000})
    assert_state(hass, entity_id, "100", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 1000})
    assert_state(hass, entity_id, "99", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 1291: 1000, 10: 5000})
    assert_state(hass, entity_id, "100", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 5000})
    assert_state(hass, entity_id, "9.9", UnitOfPower.WATT)

    assert "active_power_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x050D: 88, 10: 5000})
    assert hass.states.get(entity_id).attributes["active_power_max"] == "8.8"


async def async_test_em_apparent_power(hass: HomeAssistant, cluster, entity_id):
    """Test electrical measurement Apparent Power sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 100, 10: 1000})
    assert_state(hass, entity_id, "100", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 99, 10: 1000})
    assert_state(hass, entity_id, "99", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 1000, 10: 5000})
    assert_state(hass, entity_id, "100", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 99, 10: 5000})
    assert_state(hass, entity_id, "9.9", UnitOfApparentPower.VOLT_AMPERE)


async def async_test_em_power_factor(hass: HomeAssistant, cluster, entity_id):
    """Test electrical measurement Power Factor sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 100, 10: 1000})
    assert_state(hass, entity_id, "100", PERCENTAGE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 99, 10: 1000})
    assert_state(hass, entity_id, "99", PERCENTAGE)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 100, 10: 5000})
    assert_state(hass, entity_id, "100", PERCENTAGE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 99, 10: 5000})
    assert_state(hass, entity_id, "99", PERCENTAGE)


async def async_test_em_rms_current(hass: HomeAssistant, cluster, entity_id):
    """Test electrical measurement RMS Current sensor."""

    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 1234, 10: 1000})
    assert_state(hass, entity_id, "1.2", UnitOfElectricCurrent.AMPERE)

    await send_attributes_report(hass, cluster, {"ac_current_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 236, 10: 1000})
    assert_state(hass, entity_id, "23.6", UnitOfElectricCurrent.AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 1236, 10: 1000})
    assert_state(hass, entity_id, "124", UnitOfElectricCurrent.AMPERE)

    assert "rms_current_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x050A: 88, 10: 5000})
    assert hass.states.get(entity_id).attributes["rms_current_max"] == "8.8"


async def async_test_em_rms_voltage(hass: HomeAssistant, cluster, entity_id):
    """Test electrical measurement RMS Voltage sensor."""

    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 1234, 10: 1000})
    assert_state(hass, entity_id, "123", UnitOfElectricPotential.VOLT)

    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 234, 10: 1000})
    assert_state(hass, entity_id, "23.4", UnitOfElectricPotential.VOLT)

    await send_attributes_report(hass, cluster, {"ac_voltage_divisor": 100})
    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 2236, 10: 1000})
    assert_state(hass, entity_id, "22.4", UnitOfElectricPotential.VOLT)

    assert "rms_voltage_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x0507: 888, 10: 5000})
    assert hass.states.get(entity_id).attributes["rms_voltage_max"] == "8.9"


async def async_test_powerconfiguration(hass: HomeAssistant, cluster, entity_id):
    """Test powerconfiguration/battery sensor."""
    await send_attributes_report(hass, cluster, {33: 98})
    assert_state(hass, entity_id, "49", "%")
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.9
    assert hass.states.get(entity_id).attributes["battery_quantity"] == 3
    assert hass.states.get(entity_id).attributes["battery_size"] == "AAA"
    await send_attributes_report(hass, cluster, {32: 20})
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.0


async def async_test_powerconfiguration2(hass: HomeAssistant, cluster, entity_id):
    """Test powerconfiguration/battery sensor."""
    await send_attributes_report(hass, cluster, {33: -1})
    assert_state(hass, entity_id, STATE_UNKNOWN, "%")

    await send_attributes_report(hass, cluster, {33: 255})
    assert_state(hass, entity_id, STATE_UNKNOWN, "%")

    await send_attributes_report(hass, cluster, {33: 98})
    assert_state(hass, entity_id, "49", "%")


async def async_test_device_temperature(hass: HomeAssistant, cluster, entity_id):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {0: 2900})
    assert_state(hass, entity_id, "29.0", UnitOfTemperature.CELSIUS)


async def async_test_setpoint_change_source(hass, cluster, entity_id):
    """Test the translation of numerical state into enum text."""
    await send_attributes_report(
        hass, cluster, {Thermostat.AttributeDefs.setpoint_change_source.id: 0x01}
    )
    hass_state = hass.states.get(entity_id)
    assert hass_state.state == "Schedule"


async def async_test_pi_heating_demand(hass, cluster, entity_id):
    """Test pi heating demand is correctly returned."""
    await send_attributes_report(
        hass, cluster, {Thermostat.AttributeDefs.pi_heating_demand.id: 1}
    )
    assert_state(hass, entity_id, "1", "%")


@pytest.mark.parametrize(
    (
        "cluster_id",
        "entity_suffix",
        "test_func",
        "report_count",
        "read_plug",
        "unsupported_attrs",
        "initial_sensor_state",
    ),
    [
        (
            measurement.RelativeHumidity.cluster_id,
            "humidity",
            async_test_humidity,
            1,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.TemperatureMeasurement.cluster_id,
            "temperature",
            async_test_temperature,
            1,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.PressureMeasurement.cluster_id,
            "pressure",
            async_test_pressure,
            1,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.IlluminanceMeasurement.cluster_id,
            "illuminance",
            async_test_illuminance,
            1,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            smartenergy.Metering.cluster_id,
            "instantaneous_demand",
            async_test_metering,
            10,
            {
                "demand_formatting": 0xF9,
                "divisor": 1,
                "metering_device_type": 0x00,
                "multiplier": 1,
                "status": 0x00,
            },
            {"current_summ_delivered", "current_summ_received"},
            STATE_UNKNOWN,
        ),
        (
            smartenergy.Metering.cluster_id,
            "summation_delivered",
            async_test_smart_energy_summation_delivered,
            10,
            {
                "demand_formatting": 0xF9,
                "divisor": 1000,
                "metering_device_type": 0x00,
                "multiplier": 1,
                "status": 0x00,
                "summation_formatting": 0b1_0111_010,
                "unit_of_measure": 0x00,
            },
            {"instaneneous_demand", "current_summ_received"},
            STATE_UNKNOWN,
        ),
        (
            smartenergy.Metering.cluster_id,
            "summation_received",
            async_test_smart_energy_summation_received,
            10,
            {
                "demand_formatting": 0xF9,
                "divisor": 1000,
                "metering_device_type": 0x00,
                "multiplier": 1,
                "status": 0x00,
                "summation_formatting": 0b1_0111_010,
                "unit_of_measure": 0x00,
                "current_summ_received": 0,
            },
            {"instaneneous_demand", "current_summ_delivered"},
            "0.0",
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            "power",
            async_test_electrical_measurement,
            7,
            {"ac_power_divisor": 1000, "ac_power_multiplier": 1},
            {"apparent_power", "rms_current", "rms_voltage"},
            STATE_UNKNOWN,
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            "apparent_power",
            async_test_em_apparent_power,
            7,
            {"ac_power_divisor": 1000, "ac_power_multiplier": 1},
            {"active_power", "rms_current", "rms_voltage"},
            STATE_UNKNOWN,
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            "power_factor",
            async_test_em_power_factor,
            7,
            {"ac_power_divisor": 1000, "ac_power_multiplier": 1},
            {"active_power", "apparent_power", "rms_current", "rms_voltage"},
            STATE_UNKNOWN,
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            "current",
            async_test_em_rms_current,
            7,
            {"ac_current_divisor": 1000, "ac_current_multiplier": 1},
            {"active_power", "apparent_power", "rms_voltage"},
            STATE_UNKNOWN,
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            "voltage",
            async_test_em_rms_voltage,
            7,
            {"ac_voltage_divisor": 10, "ac_voltage_multiplier": 1},
            {"active_power", "apparent_power", "rms_current"},
            STATE_UNKNOWN,
        ),
        (
            general.PowerConfiguration.cluster_id,
            "battery",
            async_test_powerconfiguration,
            2,
            {
                "battery_size": 4,  # AAA
                "battery_voltage": 29,
                "battery_quantity": 3,
            },
            None,
            STATE_UNKNOWN,
        ),
        (
            general.PowerConfiguration.cluster_id,
            "battery",
            async_test_powerconfiguration2,
            2,
            {
                "battery_size": 4,  # AAA
                "battery_voltage": 29,
                "battery_quantity": 3,
            },
            None,
            STATE_UNKNOWN,
        ),
        (
            general.DeviceTemperature.cluster_id,
            "device_temperature",
            async_test_device_temperature,
            1,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            hvac.Thermostat.cluster_id,
            "setpoint_change_source",
            async_test_setpoint_change_source,
            10,
            None,
            None,
            STATE_UNKNOWN,
        ),
        (
            hvac.Thermostat.cluster_id,
            "pi_heating_demand",
            async_test_pi_heating_demand,
            10,
            None,
            None,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    zigpy_device_mock,
    zha_device_joined_restored,
    cluster_id,
    entity_suffix,
    test_func,
    report_count,
    read_plug,
    unsupported_attrs,
    initial_sensor_state,
) -> None:
    """Test ZHA sensor platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    if unsupported_attrs:
        for attr in unsupported_attrs:
            cluster.add_unsupported_attribute(attr)
    if cluster_id in (
        smartenergy.Metering.cluster_id,
        homeautomation.ElectricalMeasurement.cluster_id,
    ):
        # this one is mains powered
        zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100
    cluster.PLUGGED_ATTR_READS = read_plug
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = ENTITY_ID_PREFIX.format(entity_suffix)

    await async_enable_traffic(hass, [zha_device], enabled=False)
    await hass.async_block_till_done()
    # ensure the sensor entity was created
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, [zha_device])

    # test that the sensor now have their correct initial state (mostly unknown)
    assert hass.states.get(entity_id).state == initial_sensor_state

    # test sensor associated logic
    await test_func(hass, cluster, entity_id)

    # test rejoin
    await async_test_rejoin(hass, zigpy_device, [cluster], (report_count,))


def assert_state(hass: HomeAssistant, entity_id, state, unit_of_measurement):
    """Check that the state is what is expected.

    This is used to ensure that the logic in each sensor class handled the
    attribute report it received correctly.
    """
    hass_state = hass.states.get(entity_id)
    assert hass_state.state == state
    assert hass_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement


@pytest.fixture
def hass_ms(hass: HomeAssistant):
    """Hass instance with measurement system."""

    async def _hass_ms(meas_sys):
        await config_util.async_process_ha_core_config(
            hass, {CONF_UNIT_SYSTEM: meas_sys}
        )
        await hass.async_block_till_done()
        return hass

    return _hass_ms


@pytest.fixture
def core_rs(hass_storage):
    """Core.restore_state fixture."""

    def _storage(entity_id, uom, state):
        now = dt_util.utcnow().isoformat()

        hass_storage[restore_state.STORAGE_KEY] = {
            "version": restore_state.STORAGE_VERSION,
            "key": restore_state.STORAGE_KEY,
            "data": [
                {
                    "state": {
                        "entity_id": entity_id,
                        "state": str(state),
                        "attributes": {ATTR_UNIT_OF_MEASUREMENT: uom},
                        "last_changed": now,
                        "last_updated": now,
                        "context": {
                            "id": "3c2243ff5f30447eb12e7348cfd5b8ff",
                            "user_id": None,
                        },
                    },
                    "last_seen": now,
                }
            ],
        }

    return _storage


@pytest.mark.parametrize(
    ("uom", "raw_temp", "expected", "restore"),
    [
        (UnitOfTemperature.CELSIUS, 2900, 29, False),
        (UnitOfTemperature.CELSIUS, 2900, 29, True),
        (UnitOfTemperature.FAHRENHEIT, 2900, 84, False),
        (UnitOfTemperature.FAHRENHEIT, 2900, 84, True),
    ],
)
async def test_temp_uom(
    hass: HomeAssistant,
    uom,
    raw_temp,
    expected,
    restore,
    hass_ms,
    core_rs,
    zigpy_device_mock,
    zha_device_restored,
) -> None:
    """Test ZHA temperature sensor unit of measurement."""

    entity_id = "sensor.fake1026_fakemodel1026_004f3202_temperature"
    if restore:
        core_rs(entity_id, uom, state=(expected - 2))
        await async_mock_load_restore_state_from_storage(hass)

    hass = await hass_ms(
        CONF_UNIT_SYSTEM_METRIC
        if uom == UnitOfTemperature.CELSIUS
        else CONF_UNIT_SYSTEM_IMPERIAL
    )

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    measurement.TemperatureMeasurement.cluster_id,
                    general.Basic.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].temperature
    zha_device = await zha_device_restored(zigpy_device)
    entity_id = find_entity_id(Platform.SENSOR, zha_device, hass)

    if not restore:
        await async_enable_traffic(hass, [zha_device], enabled=False)
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, [zha_device])

    # test that the sensors now have a state of unknown
    if not restore:
        assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await send_attribute_report(hass, cluster, 0, raw_temp)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert round(float(state.state)) == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == uom


@patch(
    "zigpy.zcl.ClusterPersistingListener",
    MagicMock(),
)
async def test_electrical_measurement_init(
    hass: HomeAssistant,
    zigpy_device_mock,
    zha_device_joined,
) -> None:
    """Test proper initialization of the electrical measurement cluster."""

    cluster_id = homeautomation.ElectricalMeasurement.cluster_id
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    zha_device = await zha_device_joined(zigpy_device)
    entity_id = "sensor.fakemanufacturer_fakemodel_power"

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, [zha_device])

    # test that the sensor now have a state of unknown
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await send_attributes_report(hass, cluster, {0: 1, 1291: 100, 10: 1000})
    assert int(hass.states.get(entity_id).state) == 100

    cluster_handler = zha_device._endpoints[1].all_cluster_handlers["1:0x0b04"]
    assert cluster_handler.ac_power_divisor == 1
    assert cluster_handler.ac_power_multiplier == 1

    # update power divisor
    await send_attributes_report(hass, cluster, {0: 1, 1291: 20, 0x0403: 5, 10: 1000})
    assert cluster_handler.ac_power_divisor == 5
    assert cluster_handler.ac_power_multiplier == 1
    assert hass.states.get(entity_id).state == "4.0"

    await send_attributes_report(hass, cluster, {0: 1, 1291: 30, 0x0605: 10, 10: 1000})
    assert cluster_handler.ac_power_divisor == 10
    assert cluster_handler.ac_power_multiplier == 1
    assert hass.states.get(entity_id).state == "3.0"

    # update power multiplier
    await send_attributes_report(hass, cluster, {0: 1, 1291: 20, 0x0402: 6, 10: 1000})
    assert cluster_handler.ac_power_divisor == 10
    assert cluster_handler.ac_power_multiplier == 6
    assert hass.states.get(entity_id).state == "12.0"

    await send_attributes_report(hass, cluster, {0: 1, 1291: 30, 0x0604: 20, 10: 1000})
    assert cluster_handler.ac_power_divisor == 10
    assert cluster_handler.ac_power_multiplier == 20
    assert hass.states.get(entity_id).state == "60.0"


@pytest.mark.parametrize(
    ("cluster_id", "unsupported_attributes", "entity_ids", "missing_entity_ids"),
    [
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            {"apparent_power", "rms_voltage", "rms_current"},
            {
                "power",
                "ac_frequency",
                "power_factor",
            },
            {
                "apparent_power",
                "voltage",
                "current",
            },
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            {"apparent_power", "rms_current", "ac_frequency", "power_factor"},
            {"voltage", "power"},
            {
                "apparent_power",
                "current",
                "ac_frequency",
                "power_factor",
            },
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            set(),
            {
                "voltage",
                "power",
                "apparent_power",
                "current",
                "ac_frequency",
                "power_factor",
            },
            set(),
        ),
        (
            smartenergy.Metering.cluster_id,
            {
                "instantaneous_demand",
            },
            {
                "summation_delivered",
            },
            {
                "instantaneous_demand",
            },
        ),
        (
            smartenergy.Metering.cluster_id,
            {"instantaneous_demand", "current_summ_delivered"},
            {},
            {
                "instantaneous_demand",
                "summation_delivered",
            },
        ),
        (
            smartenergy.Metering.cluster_id,
            {},
            {
                "instantaneous_demand",
                "summation_delivered",
            },
            {},
        ),
    ],
)
async def test_unsupported_attributes_sensor(
    hass: HomeAssistant,
    zigpy_device_mock,
    zha_device_joined_restored,
    cluster_id,
    unsupported_attributes,
    entity_ids,
    missing_entity_ids,
) -> None:
    """Test ZHA sensor platform."""

    entity_ids = {ENTITY_ID_PREFIX.format(e) for e in entity_ids}
    missing_entity_ids = {ENTITY_ID_PREFIX.format(e) for e in missing_entity_ids}

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    if cluster_id == smartenergy.Metering.cluster_id:
        # this one is mains powered
        zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100
    for attr in unsupported_attributes:
        cluster.add_unsupported_attribute(attr)
    zha_device = await zha_device_joined_restored(zigpy_device)

    await async_enable_traffic(hass, [zha_device], enabled=False)
    await hass.async_block_till_done()
    present_entity_ids = set(find_entity_ids(Platform.SENSOR, zha_device, hass))
    assert present_entity_ids == entity_ids
    assert missing_entity_ids not in present_entity_ids


@pytest.mark.parametrize(
    ("raw_uom", "raw_value", "expected_state", "expected_uom"),
    [
        (
            1,
            12320,
            "1.23",
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            1,
            1232000,
            "123.2",
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            3,
            2340,
            "0.65",
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            3,
            2360,
            "0.68",
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            8,
            23660,
            "2.37",
            UnitOfPressure.KPA,
        ),
        (
            0,
            9366,
            "0.937",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            999,
            "0.1",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            10091,
            "1.009",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            10099,
            "1.01",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            100999,
            "10.1",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            100023,
            "10.002",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            0,
            102456,
            "10.246",
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            5,
            102456,
            "10.25",
            "IMP gal",
        ),
        (
            7,
            50124,
            "5.01",
            UnitOfVolume.LITERS,
        ),
    ],
)
async def test_se_summation_uom(
    hass: HomeAssistant,
    zigpy_device_mock,
    zha_device_joined,
    raw_uom,
    raw_value,
    expected_state,
    expected_uom,
) -> None:
    """Test ZHA smart energy summation."""

    entity_id = ENTITY_ID_PREFIX.format("summation_delivered")
    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    smartenergy.Metering.cluster_id,
                    general.Basic.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.SIMPLE_SENSOR,
            }
        }
    )
    zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100

    cluster = zigpy_device.endpoints[1].in_clusters[smartenergy.Metering.cluster_id]
    for attr in ("instanteneous_demand",):
        cluster.add_unsupported_attribute(attr)
    cluster.PLUGGED_ATTR_READS = {
        "current_summ_delivered": raw_value,
        "demand_formatting": 0xF9,
        "divisor": 10000,
        "metering_device_type": 0x00,
        "multiplier": 1,
        "status": 0x00,
        "summation_formatting": 0b1_0111_010,
        "unit_of_measure": raw_uom,
    }
    await zha_device_joined(zigpy_device)

    assert_state(hass, entity_id, expected_state, expected_uom)


@pytest.mark.parametrize(
    ("raw_measurement_type", "expected_type"),
    [
        (1, "ACTIVE_MEASUREMENT"),
        (8, "PHASE_A_MEASUREMENT"),
        (9, "ACTIVE_MEASUREMENT, PHASE_A_MEASUREMENT"),
        (
            15,
            (
                "ACTIVE_MEASUREMENT, REACTIVE_MEASUREMENT, APPARENT_MEASUREMENT,"
                " PHASE_A_MEASUREMENT"
            ),
        ),
    ],
)
async def test_elec_measurement_sensor_type(
    hass: HomeAssistant,
    elec_measurement_zigpy_dev,
    raw_measurement_type,
    expected_type,
    zha_device_joined,
) -> None:
    """Test ZHA electrical measurement sensor type."""

    entity_id = ENTITY_ID_PREFIX.format("power")
    zigpy_dev = elec_measurement_zigpy_dev
    zigpy_dev.endpoints[1].electrical_measurement.PLUGGED_ATTR_READS[
        "measurement_type"
    ] = raw_measurement_type

    await zha_device_joined(zigpy_dev)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["measurement_type"] == expected_type


async def test_elec_measurement_sensor_polling(
    hass: HomeAssistant,
    elec_measurement_zigpy_dev,
    zha_device_joined_restored,
) -> None:
    """Test ZHA electrical measurement sensor polling."""

    entity_id = ENTITY_ID_PREFIX.format("power")
    zigpy_dev = elec_measurement_zigpy_dev
    zigpy_dev.endpoints[1].electrical_measurement.PLUGGED_ATTR_READS["active_power"] = (
        20
    )

    await zha_device_joined_restored(zigpy_dev)

    # test that the sensor has an initial state of 2.0
    state = hass.states.get(entity_id)
    assert state.state == "2.0"

    # update the value for the power reading
    zigpy_dev.endpoints[1].electrical_measurement.PLUGGED_ATTR_READS["active_power"] = (
        60
    )

    # ensure the state is still 2.0
    state = hass.states.get(entity_id)
    assert state.state == "2.0"

    # let the polling happen
    future = dt_util.utcnow() + timedelta(seconds=90)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done(wait_background_tasks=True)

    # ensure the state has been updated to 6.0
    state = hass.states.get(entity_id)
    assert state.state == "6.0"


@pytest.mark.parametrize(
    "supported_attributes",
    [
        set(),
        {
            "active_power",
            "active_power_max",
            "rms_current",
            "rms_current_max",
            "rms_voltage",
            "rms_voltage_max",
        },
        {
            "active_power",
        },
        {
            "active_power",
            "active_power_max",
        },
        {
            "rms_current",
            "rms_current_max",
        },
        {
            "rms_voltage",
            "rms_voltage_max",
        },
    ],
)
async def test_elec_measurement_skip_unsupported_attribute(
    hass: HomeAssistant,
    elec_measurement_zha_dev,
    supported_attributes,
) -> None:
    """Test ZHA electrical measurement skipping update of unsupported attributes."""

    entity_id = ENTITY_ID_PREFIX.format("power")
    zha_dev = elec_measurement_zha_dev

    cluster = zha_dev.device.endpoints[1].electrical_measurement

    all_attrs = {
        "active_power",
        "active_power_max",
        "apparent_power",
        "rms_current",
        "rms_current_max",
        "rms_voltage",
        "rms_voltage_max",
        "power_factor",
        "ac_frequency",
        "ac_frequency_max",
    }
    for attr in all_attrs - supported_attributes:
        cluster.add_unsupported_attribute(attr)
    cluster.read_attributes.reset_mock()

    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert cluster.read_attributes.call_count == math.ceil(
        len(supported_attributes) / ZHA_CLUSTER_HANDLER_READS_PER_REQ
    )
    read_attrs = {
        a for call in cluster.read_attributes.call_args_list for a in call[0][0]
    }
    assert read_attrs == supported_attributes


class OppleCluster(CustomCluster, ManufacturerSpecificCluster):
    """Aqara manufacturer specific cluster."""

    cluster_id = 0xFCC0
    ep_attribute = "opple_cluster"
    attributes = {
        0x010C: ("last_feeding_size", t.uint16_t, True),
    }

    def __init__(self, *args, **kwargs) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        # populate cache to create config entity
        self._attr_cache.update({0x010C: 10})


(
    add_to_registry_v2("Fake_Manufacturer_sensor", "Fake_Model_sensor")
    .replaces(OppleCluster)
    .sensor(
        "last_feeding_size",
        OppleCluster.cluster_id,
        divisor=1,
        multiplier=1,
        unit=UnitOfMass.GRAMS,
    )
)


@pytest.fixture
async def zigpy_device_aqara_sensor_v2(
    hass: HomeAssistant, zigpy_device_mock, zha_device_joined_restored
):
    """Device tracker zigpy Aqara motion sensor device."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    OppleCluster.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.OCCUPANCY_SENSOR,
            }
        },
        manufacturer="Fake_Manufacturer_sensor",
        model="Fake_Model_sensor",
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].opple_cluster


async def test_last_feeding_size_sensor_v2(
    hass: HomeAssistant, zigpy_device_aqara_sensor_v2
) -> None:
    """Test quirks defined sensor."""

    zha_device, cluster = zigpy_device_aqara_sensor_v2
    assert isinstance(zha_device.device, CustomDeviceV2)
    entity_id = find_entity_id(
        Platform.SENSOR, zha_device, hass, qualifier="last_feeding_size"
    )
    assert entity_id is not None

    await send_attributes_report(hass, cluster, {0x010C: 1})
    assert_state(hass, entity_id, "1.0", UnitOfMass.GRAMS.value)

    await send_attributes_report(hass, cluster, {0x010C: 5})
    assert_state(hass, entity_id, "5.0", UnitOfMass.GRAMS.value)


@pytest.fixture
async def coordinator(hass: HomeAssistant, zigpy_device_mock, zha_device_joined):
    """Test ZHA fan platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Groups.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.CONTROL_BRIDGE,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        },
        ieee="00:15:8d:00:02:32:4f:32",
        nwk=0x0000,
        node_descriptor=b"\xf8\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff",
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


async def test_device_counter_sensors(
    hass: HomeAssistant,
    coordinator: ZHADevice,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test quirks defined sensor."""

    entity_id = "sensor.coordinator_manufacturer_coordinator_model_counter_1"
    state = hass.states.get(entity_id)
    assert state is None

    # Enable the entity.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1"

    # simulate counter increment on application
    coordinator.device.application.state.counters["ezsp_counters"][
        "counter_1"
    ].increment()

    next_update = dt_util.utcnow() + timedelta(seconds=60)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2"
