"""Test zha binary sensor."""
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.measurement as measurement
import zigpy.zcl.clusters.security as security
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    async_test_device_join,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)


async def test_binary_sensor(hass, config_entry, zha_gateway):
    """Test zha binary_sensor platform."""

    # create zigpy devices
    zigpy_device_zone = await async_init_zigpy_device(
        hass,
        [security.IasZone.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
        ieee="00:0d:6f:11:9a:90:69:e6",
    )

    zigpy_device_occupancy = await async_init_zigpy_device(
        hass,
        [measurement.OccupancySensing.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
        ieee="00:0d:6f:11:9a:90:69:e7",
        manufacturer="FakeOccupancy",
        model="FakeOccupancyModel",
    )

    # load up binary_sensor domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    # on off binary_sensor
    zone_cluster = zigpy_device_zone.endpoints.get(1).ias_zone
    zone_zha_device = zha_gateway.get_device(zigpy_device_zone.ieee)
    zone_entity_id = await find_entity_id(DOMAIN, zone_zha_device, hass)
    assert zone_entity_id is not None

    # occupancy binary_sensor
    occupancy_cluster = zigpy_device_occupancy.endpoints.get(1).occupancy
    occupancy_zha_device = zha_gateway.get_device(zigpy_device_occupancy.ieee)
    occupancy_entity_id = await find_entity_id(DOMAIN, occupancy_zha_device, hass)
    assert occupancy_entity_id is not None

    # test that the sensors exist and are in the unavailable state
    assert hass.states.get(zone_entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(occupancy_entity_id).state == STATE_UNAVAILABLE

    await async_enable_traffic(
        hass, zha_gateway, [zone_zha_device, occupancy_zha_device]
    )

    # test that the sensors exist and are in the off state
    assert hass.states.get(zone_entity_id).state == STATE_OFF
    assert hass.states.get(occupancy_entity_id).state == STATE_OFF

    # test getting messages that trigger and reset the sensors
    await async_test_binary_sensor_on_off(hass, occupancy_cluster, occupancy_entity_id)

    # test IASZone binary sensors
    await async_test_iaszone_on_off(hass, zone_cluster, zone_entity_id)

    # test new sensor join
    await async_test_device_join(
        hass, zha_gateway, measurement.OccupancySensing.cluster_id, occupancy_entity_id
    )


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
