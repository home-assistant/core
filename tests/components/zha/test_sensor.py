"""Test ZHA sensor."""

from unittest.mock import patch

import pytest
from zigpy.profiles import zha
from zigpy.zcl import Cluster
from zigpy.zcl.clusters import general, homeautomation, hvac, measurement, smartenergy
from zigpy.zcl.clusters.hvac import Thermostat

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.zha.helpers import get_zha_gateway
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNKNOWN,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from .common import send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ENTITY_ID_NO_PREFIX = "sensor.fakemanufacturer_fakemodel"
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


async def async_test_humidity(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test humidity sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 100})
    assert_state(hass, entity_id, "10.0", PERCENTAGE)


async def async_test_temperature(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 2900, 2: 100})
    assert_state(hass, entity_id, "29.0", UnitOfTemperature.CELSIUS)


async def async_test_pressure(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test pressure sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 10000})
    assert_state(hass, entity_id, "1000.0", UnitOfPressure.HPA)

    await send_attributes_report(hass, cluster, {0: 1000, 20: -1, 16: 10000})
    assert_state(hass, entity_id, "1000.0", UnitOfPressure.HPA)


async def async_test_illuminance(hass: HomeAssistant, cluster: Cluster, entity_id: str):
    """Test illuminance sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 10, 2: 20})
    assert_state(hass, entity_id, "1", LIGHT_LUX)

    await send_attributes_report(hass, cluster, {1: 0, 0: 0, 2: 20})
    assert_state(hass, entity_id, "0", LIGHT_LUX)

    await send_attributes_report(hass, cluster, {1: 0, 0: 0xFFFF, 2: 20})
    assert_state(hass, entity_id, "unknown", LIGHT_LUX)


async def async_test_metering(hass: HomeAssistant, cluster: Cluster, entity_id: str):
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
        hass, cluster, {"metering_device_type": 1, "status": 64 + 8}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|NOT_DEFINED",
        "NOT_DEFINED|SERVICE_DISCONNECT",
    )

    await send_attributes_report(
        hass, cluster, {"metering_device_type": 2, "status": 64 + 8}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|PIPE_EMPTY",
        "PIPE_EMPTY|SERVICE_DISCONNECT",
    )

    await send_attributes_report(
        hass, cluster, {"metering_device_type": 5, "status": 64 + 8}
    )
    assert hass.states.get(entity_id).attributes["status"] in (
        "SERVICE_DISCONNECT|TEMPERATURE_SENSOR",
        "TEMPERATURE_SENSOR|SERVICE_DISCONNECT",
    )

    # Status for other meter types
    await send_attributes_report(
        hass, cluster, {"metering_device_type": 4, "status": 32}
    )
    assert hass.states.get(entity_id).attributes["status"] in ("<bitmap8.32: 32>", "32")


async def async_test_smart_energy_summation_delivered(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
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
    hass: HomeAssistant, cluster: Cluster, entity_id: str
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


async def async_test_electrical_measurement(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test electrical measurement sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 1291: 100, 10: 1000})
    assert_state(hass, entity_id, "100.0", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 1000})
    assert_state(hass, entity_id, "99.0", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 1291: 1000, 10: 5000})
    assert_state(hass, entity_id, "100.0", UnitOfPower.WATT)

    await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 5000})
    assert_state(hass, entity_id, "9.9", UnitOfPower.WATT)

    assert "active_power_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x050D: 88, 10: 5000})
    assert hass.states.get(entity_id).attributes["active_power_max"] == 8.8


async def async_test_em_apparent_power(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test electrical measurement Apparent Power sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 100, 10: 1000})
    assert_state(hass, entity_id, "100.0", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 99, 10: 1000})
    assert_state(hass, entity_id, "99.0", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 1000, 10: 5000})
    assert_state(hass, entity_id, "100.0", UnitOfApparentPower.VOLT_AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x050F: 99, 10: 5000})
    assert_state(hass, entity_id, "9.9", UnitOfApparentPower.VOLT_AMPERE)


async def async_test_em_power_factor(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test electrical measurement Power Factor sensor."""
    # update divisor cached value
    await send_attributes_report(hass, cluster, {"ac_power_divisor": 1})
    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 100, 10: 1000})
    assert_state(hass, entity_id, "100.0", PERCENTAGE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 99, 10: 1000})
    assert_state(hass, entity_id, "99.0", PERCENTAGE)

    await send_attributes_report(hass, cluster, {"ac_power_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 100, 10: 5000})
    assert_state(hass, entity_id, "100.0", PERCENTAGE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0510: 99, 10: 5000})
    assert_state(hass, entity_id, "99.0", PERCENTAGE)


async def async_test_em_rms_current(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test electrical measurement RMS Current sensor."""

    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 1234, 10: 1000})
    assert_state(hass, entity_id, "1.234", UnitOfElectricCurrent.AMPERE)

    await send_attributes_report(hass, cluster, {"ac_current_divisor": 10})
    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 236, 10: 1000})
    assert_state(hass, entity_id, "23.6", UnitOfElectricCurrent.AMPERE)

    await send_attributes_report(hass, cluster, {0: 1, 0x0508: 1236, 10: 1000})
    assert_state(hass, entity_id, "123.6", UnitOfElectricCurrent.AMPERE)

    assert "rms_current_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x050A: 88, 10: 5000})
    assert hass.states.get(entity_id).attributes["rms_current_max"] == 8.8


async def async_test_em_rms_voltage(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test electrical measurement RMS Voltage sensor."""

    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 1234, 10: 1000})
    assert_state(hass, entity_id, "123.4", UnitOfElectricPotential.VOLT)

    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 234, 10: 1000})
    assert_state(hass, entity_id, "23.4", UnitOfElectricPotential.VOLT)

    await send_attributes_report(hass, cluster, {"ac_voltage_divisor": 100})
    await send_attributes_report(hass, cluster, {0: 1, 0x0505: 2236, 10: 1000})
    assert_state(hass, entity_id, "22.36", UnitOfElectricPotential.VOLT)

    assert "rms_voltage_max" not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster, {0: 1, 0x0507: 888, 10: 5000})
    assert hass.states.get(entity_id).attributes["rms_voltage_max"] == 8.88


async def async_test_powerconfiguration(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test powerconfiguration/battery sensor."""
    await send_attributes_report(hass, cluster, {33: 98})
    assert_state(hass, entity_id, "49.0", "%")
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.9
    assert hass.states.get(entity_id).attributes["battery_quantity"] == 3
    assert hass.states.get(entity_id).attributes["battery_size"] == "AAA"
    await send_attributes_report(hass, cluster, {32: 20})
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.0


async def async_test_powerconfiguration2(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test powerconfiguration/battery sensor."""
    await send_attributes_report(hass, cluster, {33: -1})
    assert_state(hass, entity_id, STATE_UNKNOWN, "%")

    await send_attributes_report(hass, cluster, {33: 255})
    assert_state(hass, entity_id, STATE_UNKNOWN, "%")

    await send_attributes_report(hass, cluster, {33: 98})
    assert_state(hass, entity_id, "49.0", "%")


async def async_test_device_temperature(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {0: 2900})
    assert_state(hass, entity_id, "29.0", UnitOfTemperature.CELSIUS)


async def async_test_setpoint_change_source(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test the translation of numerical state into enum text."""
    await send_attributes_report(
        hass, cluster, {Thermostat.AttributeDefs.setpoint_change_source.id: 0x01}
    )
    hass_state = hass.states.get(entity_id)
    assert hass_state.state == "Schedule"


async def async_test_pi_heating_demand(
    hass: HomeAssistant, cluster: Cluster, entity_id: str
):
    """Test pi heating demand is correctly returned."""
    await send_attributes_report(
        hass, cluster, {Thermostat.AttributeDefs.pi_heating_demand.id: 1}
    )
    assert_state(hass, entity_id, "1.0", "%")


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
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.TemperatureMeasurement.cluster_id,
            "temperature",
            async_test_temperature,
            1,
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.PressureMeasurement.cluster_id,
            "pressure",
            async_test_pressure,
            1,
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            measurement.IlluminanceMeasurement.cluster_id,
            "illuminance",
            async_test_illuminance,
            1,
            {},
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
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            hvac.Thermostat.cluster_id,
            "setpoint_change_source",
            async_test_setpoint_change_source,
            10,
            {},
            None,
            STATE_UNKNOWN,
        ),
        (
            hvac.Thermostat.cluster_id,
            "pi_heating_demand",
            async_test_pi_heating_demand,
            10,
            {},
            None,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    setup_zha,
    zigpy_device_mock,
    cluster_id,
    entity_suffix,
    test_func,
    report_count,
    read_plug,
    unsupported_attrs,
    initial_sensor_state,
) -> None:
    """Test ZHA sensor platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
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

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )

    if hass.states.get(ENTITY_ID_NO_PREFIX):
        entity_id = ENTITY_ID_NO_PREFIX
    else:
        entity_id = ENTITY_ID_PREFIX.format(entity_suffix)

    assert hass.states.get(entity_id).state == initial_sensor_state

    # test sensor associated logic
    await test_func(hass, cluster, entity_id)


def assert_state(hass: HomeAssistant, entity_id, state, unit_of_measurement):
    """Check that the state is what is expected.

    This is used to ensure that the logic in each sensor class handled the
    attribute report it received correctly.
    """
    hass_state = hass.states.get(entity_id)
    assert hass_state.state == state
    assert hass_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement
