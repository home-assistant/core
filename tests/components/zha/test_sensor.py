"""Test zha sensor."""
from unittest import mock

import pytest
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
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
    assert_state(hass, entity_id, "10.0", UNIT_PERCENTAGE)


async def async_test_temperature(hass, cluster, entity_id):
    """Test temperature sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 2900, 2: 100})
    assert_state(hass, entity_id, "29.0", TEMP_CELSIUS)


async def async_test_pressure(hass, cluster, entity_id):
    """Test pressure sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 1000, 2: 10000})
    assert_state(hass, entity_id, "1000", "hPa")

    await send_attributes_report(hass, cluster, {0: 1000, 20: -1, 16: 10000})
    assert_state(hass, entity_id, "1000", "hPa")


async def async_test_illuminance(hass, cluster, entity_id):
    """Test illuminance sensor."""
    await send_attributes_report(hass, cluster, {1: 1, 0: 10, 2: 20})
    assert_state(hass, entity_id, "1.0", "lx")


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
        assert_state(hass, entity_id, "100", "W")

        await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 1000})
        assert_state(hass, entity_id, "99", "W")

        divisor_mock.return_value = 10
        await send_attributes_report(hass, cluster, {0: 1, 1291: 1000, 10: 5000})
        assert_state(hass, entity_id, "100", "W")

        await send_attributes_report(hass, cluster, {0: 1, 1291: 99, 10: 5000})
        assert_state(hass, entity_id, "9.9", "W")


@pytest.mark.parametrize(
    "cluster_id, test_func, report_count",
    (
        (measurement.RelativeHumidity.cluster_id, async_test_humidity, 1),
        (measurement.TemperatureMeasurement.cluster_id, async_test_temperature, 1),
        (measurement.PressureMeasurement.cluster_id, async_test_pressure, 1),
        (measurement.IlluminanceMeasurement.cluster_id, async_test_illuminance, 1),
        (smartenergy.Metering.cluster_id, async_test_metering, 1),
        (
            homeautomation.ElectricalMeasurement.cluster_id,
            async_test_electrical_measurement,
            1,
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
):
    """Test zha sensor platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [cluster_id, general.Basic.cluster_id],
                "out_cluster": [],
                "device_type": 0x0000,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].in_clusters[cluster_id]
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

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
                "device_type": 0x0000,
            }
        }
    )
    cluster = zigpy_device.endpoints[1].temperature
    zha_device = await zha_device_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

    if not restore:
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
