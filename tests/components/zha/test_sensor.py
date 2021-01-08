"""Test zha sensor."""
from unittest import mock

import pytest
import zigpy.profiles.zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.homeautomation as homeautomation
import zigpy.zcl.clusters.measurement as measurement
import zigpy.zcl.clusters.smartenergy as smartenergy

from homeassistant.components.sensor import DOMAIN
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers import restore_state
from homeassistant.util import dt as dt_util

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    send_attribute_report,
    send_attributes_report,
)


async def async_test_humidity(hass, cluster, entity_id):
    """Test humidity sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 100})
    assert_state(hass, entity_id, "10.0", PERCENTAGE)


async def async_test_temperature(hass, cluster, entity_id):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 2900, 2: 100})
    assert_state(hass, entity_id, "29.0", TEMP_CELSIUS)


async def async_test_pressure(hass, cluster, entity_id):
    """Test pressure sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 10000})
    assert_state(hass, entity_id, "1000", PRESSURE_HPA)

    await send_attributes_report(hass, cluster, {0: 1000, 20: -1, 16: 10000})
    assert_state(hass, entity_id, "1000", PRESSURE_HPA)


async def async_test_illuminance(hass, cluster, entity_id):
    """Test illuminance sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 10, 2: 20})
    assert_state(hass, entity_id, "1.0", LIGHT_LUX)


async def async_test_metering(hass, cluster, entity_id):
    """Test metering sensor."""
    await send_attributes_report(hass, cluster, {1025: 1, 1024: 12345, 1026: 100})
    assert_state(hass, entity_id, "12345.0", "unknown")


async def async_test_electrical_measurement(hass, cluster, entity_id):
    """Test electrical measurement sensor."""
    with mock.patch(
        (
            "homeassistant.components.zha.core.channels.homeautomation"
            ".ElectricalMeasurementChannel.divisor"
        ),
        new_callable=mock.PropertyMock,
    ) as divisor_mock:
        divisor_mock.return_value = 1
        await send_attributes_report(hass, cluster, {0: 1, 1291: 100, 10: 1000})
        assert_state(hass, entity_id, "100", POWER_WATT)

        await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 1000})
        assert_state(hass, entity_id, "99", POWER_WATT)

        divisor_mock.return_value = 10
        await send_attributes_report(hass, cluster, {0: 1, 1291: 1000, 10: 5000})
        assert_state(hass, entity_id, "100", POWER_WATT)

        await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 5000})
        assert_state(hass, entity_id, "9.9", POWER_WATT)


async def async_test_powerconfiguration(hass, cluster, entity_id):
    """Test powerconfiguration/battery sensor."""
    await send_attributes_report(hass, cluster, {33: 98})
    assert_state(hass, entity_id, "49", "%")
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.9
    assert hass.states.get(entity_id).attributes["battery_quantity"] == 3
    assert hass.states.get(entity_id).attributes["battery_size"] == "AAA"
    await send_attributes_report(hass, cluster, {32: 20})
    assert hass.states.get(entity_id).attributes["battery_voltage"] == 2.0


@pytest.mark.parametrize(
    "cluster_id, test_func, report_count, read_plug",
    (
        (measurement.RelativeHumidity.cluster_id, async_test_humidity, 1, None),
        (
            measurement.TemperatureMeasurement.cluster_id,
            async_test_temperature,
            1,
            None,
        ),
        (measurement.PressureMeasurement.cluster_id, async_test_pressure, 1, None),
        (
            measurement.IlluminanceMeasurement.cluster_id,
            async_test_illuminance,
            1,
            None,
        ),
        (
            smartenergy.Metering.cluster_id,
            async_test_metering,
            1,
            {
                "demand_formatting": 0xF9,
                "divisor": 1,
                "multiplier": 1,
            },
        ),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            async_test_electrical_measurement,
            1,
            None,
        ),
        (
            general.PowerConfiguration.cluster_id,
            async_test_powerconfiguration,
            2,
            {
                "battery_size": 4,  # AAA
                "battery_voltage": 29,
                "battery_quantity": 3,
            },
        ),
    ),
)
async def test_sensor(
    hass,
    zigpy_device_mock,
    zha_device_joined_restored,
    cluster_id,
    test_func,
    report_count,
    read_plug,
):
    """Test zha sensor platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [cluster_id, general.Basic.cluster_id],
                "out_cluster": [],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    if cluster_id == smartenergy.Metering.cluster_id:
        # this one is mains powered
        zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100
    cluster.PLUGGED_ATTR_READS = read_plug
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

    await async_enable_traffic(hass, [zha_device], enabled=False)
    await hass.async_block_till_done()
    # ensure the sensor entity was created
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, [zha_device])

    # test that the sensor now have a state of unknown
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # test sensor associated logic
    await test_func(hass, cluster, entity_id)

    # test rejoin
    await async_test_rejoin(hass, zigpy_device, [cluster], (report_count,))


def assert_state(hass, entity_id, state, unit_of_measurement):
    """Check that the state is what is expected.

    This is used to ensure that the logic in each sensor class handled the
    attribute report it received correctly.
    """
    hass_state = hass.states.get(entity_id)
    assert hass_state.state == state
    assert hass_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement


@pytest.fixture
def hass_ms(hass):
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
        return

    return _storage


@pytest.mark.parametrize(
    "uom, raw_temp, expected, restore",
    [
        (TEMP_CELSIUS, 2900, 29, False),
        (TEMP_CELSIUS, 2900, 29, True),
        (TEMP_FAHRENHEIT, 2900, 84, False),
        (TEMP_FAHRENHEIT, 2900, 84, True),
    ],
)
async def test_temp_uom(
    uom,
    raw_temp,
    expected,
    restore,
    hass_ms,
    core_rs,
    zigpy_device_mock,
    zha_device_restored,
):
    """Test zha temperature sensor unit of measurement."""

    entity_id = "sensor.fake1026_fakemodel1026_004f3202_temperature"
    if restore:
        core_rs(entity_id, uom, state=(expected - 2))

    hass = await hass_ms(
        CONF_UNIT_SYSTEM_METRIC if uom == TEMP_CELSIUS else CONF_UNIT_SYSTEM_IMPERIAL
    )

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [
                    measurement.TemperatureMeasurement.cluster_id,
                    general.Basic.cluster_id,
                ],
                "out_cluster": [],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].temperature
    zha_device = await zha_device_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

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


async def test_electrical_measurement_init(
    hass,
    zigpy_device_mock,
    zha_device_joined,
):
    """Test proper initialization of the electrical measurement cluster."""

    cluster_id = homeautomation.ElectricalMeasurement.cluster_id
    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [cluster_id, general.Basic.cluster_id],
                "out_cluster": [],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    zha_device = await zha_device_joined(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, [zha_device])

    # test that the sensor now have a state of unknown
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await send_attributes_report(hass, cluster, {0: 1, 1291: 100, 10: 1000})
    assert int(hass.states.get(entity_id).state) == 100

    channel = zha_device.channels.pools[0].all_channels["1:0x0b04"]
    assert channel.divisor == 1
    assert channel.multiplier == 1

    # update power divisor
    await send_attributes_report(hass, cluster, {0: 1, 1291: 20, 0x0403: 5, 10: 1000})
    assert channel.divisor == 5
    assert channel.multiplier == 1
    assert hass.states.get(entity_id).state == "4.0"

    await send_attributes_report(hass, cluster, {0: 1, 1291: 30, 0x0605: 10, 10: 1000})
    assert channel.divisor == 10
    assert channel.multiplier == 1
    assert hass.states.get(entity_id).state == "3.0"

    # update power multiplier
    await send_attributes_report(hass, cluster, {0: 1, 1291: 20, 0x0402: 6, 10: 1000})
    assert channel.divisor == 10
    assert channel.multiplier == 6
    assert hass.states.get(entity_id).state == "12.0"

    await send_attributes_report(hass, cluster, {0: 1, 1291: 30, 0x0604: 20, 10: 1000})
    assert channel.divisor == 10
    assert channel.multiplier == 20
    assert hass.states.get(entity_id).state == "60.0"
