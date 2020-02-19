"""Test zha binary sensor."""
import pytest
import zigpy.zcl.clusters.measurement as measurement
import zigpy.zcl.clusters.security as security
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

DEVICE_IAS = {
    1: {
        "device_type": 1026,
        "in_clusters": [security.IasZone.cluster_id],
        "out_clusters": [],
    }
}


DEVICE_OCCUPANCY = {
    1: {
        "device_type": 263,
        "in_clusters": [measurement.OccupancySensing.cluster_id],
        "out_clusters": [],
    }
}


async def async_test_binary_sensor_on_off(hass, cluster, entity_id):
    """Test getting on and off messages for binary sensors."""
    # binary sensor on
    attr = make_attribute(0, 1)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)

    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # binary sensor off
    attr.value.value = 0
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def async_test_iaszone_on_off(hass, cluster, entity_id):
    """Test getting on and off messages for iaszone binary sensors."""
    # binary sensor on
    cluster.listener_event("cluster_command", 1, 0, [1])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # binary sensor off
    cluster.listener_event("cluster_command", 1, 0, [0])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "device, on_off_test, cluster_name, reporting",
    [
        (DEVICE_IAS, async_test_iaszone_on_off, "ias_zone", (0,)),
        (DEVICE_OCCUPANCY, async_test_binary_sensor_on_off, "occupancy", (1,)),
    ],
)
async def test_binary_sensor(
    hass,
    zigpy_device_mock,
    zha_device_joined_restored,
    device,
    on_off_test,
    cluster_name,
    reporting,
):
    """Test ZHA binary_sensor platform."""
    zigpy_device = zigpy_device_mock(device)
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

    assert entity_id is not None

    # test that the sensors exist and are in the unavailable state
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await async_enable_traffic(hass, [zha_device])

    # test that the sensors exist and are in the off state
    assert hass.states.get(entity_id).state == STATE_OFF

    # test getting messages that trigger and reset the sensors
    cluster = getattr(zigpy_device.endpoints[1], cluster_name)
    await on_off_test(hass, cluster, entity_id)

    # test rejoin
    await async_test_rejoin(hass, zigpy_device, [cluster], reporting)
    assert hass.states.get(entity_id).state == STATE_OFF
