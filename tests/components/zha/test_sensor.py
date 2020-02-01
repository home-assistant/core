"""Test zha sensor."""
from unittest import mock

import pytest
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.homeautomation as homeautomation
import zigpy.zcl.clusters.measurement as measurement
import zigpy.zcl.clusters.smartenergy as smartenergy
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.sensor import DOMAIN
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers import restore_state
from homeassistant.util import dt as dt_util

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    async_test_device_join,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)


async def test_sensor(hass, config_entry, zha_gateway):
    """Test zha sensor platform."""

    # list of cluster ids to create devices and sensor entities for
    cluster_ids = [
        measurement.RelativeHumidity.cluster_id,
        measurement.TemperatureMeasurement.cluster_id,
        measurement.PressureMeasurement.cluster_id,
        measurement.IlluminanceMeasurement.cluster_id,
        smartenergy.Metering.cluster_id,
        homeautomation.ElectricalMeasurement.cluster_id,
    ]

    # devices that were created from cluster_ids list above
    zigpy_device_infos = await async_build_devices(
        hass, zha_gateway, config_entry, cluster_ids
    )

    # ensure the sensor entity was created for each id in cluster_ids
    for cluster_id in cluster_ids:
        zigpy_device_info = zigpy_device_infos[cluster_id]
        entity_id = zigpy_device_info[ATTR_ENTITY_ID]
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(
        hass,
        zha_gateway,
        [
            zigpy_device_info["zha_device"]
            for zigpy_device_info in zigpy_device_infos.values()
        ],
    )

    # test that the sensors now have a state of unknown
    for cluster_id in cluster_ids:
        zigpy_device_info = zigpy_device_infos[cluster_id]
        entity_id = zigpy_device_info[ATTR_ENTITY_ID]
        assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # get the humidity device info and test the associated sensor logic
    device_info = zigpy_device_infos[measurement.RelativeHumidity.cluster_id]
    await async_test_humidity(hass, device_info)

    # get the temperature device info and test the associated sensor logic
    device_info = zigpy_device_infos[measurement.TemperatureMeasurement.cluster_id]
    await async_test_temperature(hass, device_info)

    # get the pressure device info and test the associated sensor logic
    device_info = zigpy_device_infos[measurement.PressureMeasurement.cluster_id]
    await async_test_pressure(hass, device_info)

    # get the illuminance device info and test the associated sensor logic
    device_info = zigpy_device_infos[measurement.IlluminanceMeasurement.cluster_id]
    await async_test_illuminance(hass, device_info)

    # get the metering device info and test the associated sensor logic
    device_info = zigpy_device_infos[smartenergy.Metering.cluster_id]
    await async_test_metering(hass, device_info)

    # get the electrical_measurement device info and test the associated
    # sensor logic
    device_info = zigpy_device_infos[homeautomation.ElectricalMeasurement.cluster_id]
    await async_test_electrical_measurement(hass, device_info)

    # test joining a new temperature sensor to the network
    await async_test_device_join(
        hass, zha_gateway, measurement.TemperatureMeasurement.cluster_id, entity_id
    )


async def async_build_devices(hass, zha_gateway, config_entry, cluster_ids):
    """Build a zigpy device for each cluster id.

    This will build devices for all cluster ids that exist in cluster_ids.
    They get added to the network and then the sensor component is loaded
    which will cause sensor entities to get created for each device.
    A dict containing relevant device info for testing is returned. It contains
    the entity id, zigpy device, and the zigbee cluster for the sensor.
    """

    device_infos = {}
    counter = 0
    for cluster_id in cluster_ids:
        # create zigpy device
        device_infos[cluster_id] = {"zigpy_device": None}
        device_infos[cluster_id]["zigpy_device"] = await async_init_zigpy_device(
            hass,
            [cluster_id, general.Basic.cluster_id],
            [],
            None,
            zha_gateway,
            ieee=f"00:15:8d:00:02:32:4f:0{counter}",
            manufacturer=f"Fake{cluster_id}",
            model=f"FakeModel{cluster_id}",
        )

        counter += 1

    # load up sensor domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    # put the other relevant info in the device info dict
    for cluster_id in cluster_ids:
        device_info = device_infos[cluster_id]
        zigpy_device = device_info["zigpy_device"]
        device_info["cluster"] = zigpy_device.endpoints.get(1).in_clusters[cluster_id]
        zha_device = zha_gateway.get_device(zigpy_device.ieee)
        device_info["zha_device"] = zha_device
        device_info[ATTR_ENTITY_ID] = await find_entity_id(DOMAIN, zha_device, hass)
    await hass.async_block_till_done()
    return device_infos


async def async_test_humidity(hass, device_info):
    """Test humidity sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 1000)
    assert_state(hass, device_info, "10.0", "%")


async def async_test_temperature(hass, device_info):
    """Test temperature sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 2900)
    assert_state(hass, device_info, "29.0", "°C")


async def async_test_pressure(hass, device_info):
    """Test pressure sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 1000)
    assert_state(hass, device_info, "1000", "hPa")


async def async_test_illuminance(hass, device_info):
    """Test illuminance sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 10)
    assert_state(hass, device_info, "1.0", "lx")


async def async_test_metering(hass, device_info):
    """Test metering sensor."""
    await send_attribute_report(hass, device_info["cluster"], 1024, 12345)
    assert_state(hass, device_info, "12345.0", "unknown")


async def async_test_electrical_measurement(hass, device_info):
    """Test electrical measurement sensor."""
    with mock.patch(
        (
            "homeassistant.components.zha.core.channels.homeautomation"
            ".ElectricalMeasurementChannel.divisor"
        ),
        new_callable=mock.PropertyMock,
    ) as divisor_mock:
        divisor_mock.return_value = 1
        await send_attribute_report(hass, device_info["cluster"], 1291, 100)
        assert_state(hass, device_info, "100", "W")

        await send_attribute_report(hass, device_info["cluster"], 1291, 99)
        assert_state(hass, device_info, "99", "W")

        divisor_mock.return_value = 10
        await send_attribute_report(hass, device_info["cluster"], 1291, 1000)
        assert_state(hass, device_info, "100", "W")

        await send_attribute_report(hass, device_info["cluster"], 1291, 99)
        assert_state(hass, device_info, "9.9", "W")


async def send_attribute_report(hass, cluster, attrid, value):
    """Cause the sensor to receive an attribute report from the network.

    This is to simulate the normal device communication that happens when a
    device is paired to the zigbee network.
    """
    attr = make_attribute(attrid, value)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()


def assert_state(hass, device_info, state, unit_of_measurement):
    """Check that the state is what is expected.

    This is used to ensure that the logic in each sensor class handled the
    attribute report it received correctly.
    """
    hass_state = hass.states.get(device_info[ATTR_ENTITY_ID])
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
    uom, raw_temp, expected, restore, hass_ms, config_entry, zha_gateway, core_rs
):
    """Test zha temperature sensor unit of measurement."""

    entity_id = "sensor.fake1026_fakemodel1026_004f3202_temperature"
    if restore:
        core_rs(entity_id, uom, state=(expected - 2))

    hass = await hass_ms(
        CONF_UNIT_SYSTEM_METRIC if uom == TEMP_CELSIUS else CONF_UNIT_SYSTEM_IMPERIAL
    )

    # list of cluster ids to create devices and sensor entities for
    temp_cluster = measurement.TemperatureMeasurement
    cluster_ids = [temp_cluster.cluster_id]

    # devices that were created from cluster_ids list above
    zigpy_device_infos = await async_build_devices(
        hass, zha_gateway, config_entry, cluster_ids
    )

    zigpy_device_info = zigpy_device_infos[temp_cluster.cluster_id]
    zha_device = zigpy_device_info["zha_device"]
    if not restore:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and devices
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the sensors now have a state of unknown
    if not restore:
        assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await send_attribute_report(hass, zigpy_device_info["cluster"], 0, raw_temp)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert round(float(state.state)) == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == uom
