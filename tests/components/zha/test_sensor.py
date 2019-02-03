"""Test zha sensor."""
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from .common import (
    async_init_zigpy_device, make_attribute, make_entity_id,
    async_test_device_join
)


async def test_sensor(hass, config_entry, zha_gateway):
    """Test zha sensor platform."""
    from zigpy.zcl.clusters.measurement import (
        RelativeHumidity, TemperatureMeasurement, PressureMeasurement,
        IlluminanceMeasurement
    )
    from zigpy.zcl.clusters.smartenergy import Metering
    from zigpy.zcl.clusters.homeautomation import ElectricalMeasurement
    # from zigpy.zcl.clusters.general import PowerConfiguration

    cluster_ids = [
        RelativeHumidity.cluster_id,
        TemperatureMeasurement.cluster_id,
        PressureMeasurement.cluster_id,
        IlluminanceMeasurement.cluster_id,
        Metering.cluster_id,
        ElectricalMeasurement.cluster_id,
        # PowerConfiguration.cluster_id
    ]

    zigpy_device_infos = await async_build_devices(
        hass, zha_gateway, config_entry, cluster_ids)

    for cluster_id in cluster_ids:
        zigpy_device_info = zigpy_device_infos[cluster_id]
        entity_id = zigpy_device_info["entity_id"]
        assert hass.states.get(entity_id).state == STATE_UNKNOWN

    device_info = zigpy_device_infos[RelativeHumidity.cluster_id]
    await async_test_humidity(hass, device_info)

    device_info = zigpy_device_infos[TemperatureMeasurement.cluster_id]
    await async_test_temperature(hass, device_info)

    device_info = zigpy_device_infos[PressureMeasurement.cluster_id]
    await async_test_pressure(hass, device_info)

    device_info = zigpy_device_infos[IlluminanceMeasurement.cluster_id]
    await async_test_illuminance(hass, device_info)

    device_info = zigpy_device_infos[Metering.cluster_id]
    await async_test_metering(hass, device_info)

    device_info = zigpy_device_infos[ElectricalMeasurement.cluster_id]
    await async_test_electrical_measurement(hass, device_info)

    await async_test_device_join(
        hass, zha_gateway, TemperatureMeasurement.cluster_id, DOMAIN)


async def async_build_devices(hass, zha_gateway, config_entry, cluster_ids):
    """Build a zigpy device for each cluster id."""
    device_infos = {}
    counter = 0
    for cluster_id in cluster_ids:
        # create zigpy device
        device_infos[cluster_id] = {"zigpy_device": None}
        device_infos[cluster_id]["zigpy_device"] = await \
            async_init_zigpy_device(
                hass, [cluster_id], [], None, zha_gateway,
                ieee="{}0:15:8d:00:02:32:4f:32".format(counter),
                manufacturer="Fake{}".format(cluster_id),
                model="FakeModel{}".format(cluster_id))

        counter += 1

    # load up sensor domain
    await hass.config_entries.async_forward_entry_setup(
        config_entry, DOMAIN)
    await hass.async_block_till_done()

    for cluster_id in cluster_ids:
        device_info = device_infos[cluster_id]
        zigpy_device = device_info["zigpy_device"]
        device_info["cluster"] = zigpy_device.endpoints.get(
            1).in_clusters[cluster_id]
        device_info["entity_id"] = make_entity_id(
            DOMAIN, zigpy_device, device_info["cluster"])
    return device_infos


async def async_test_humidity(hass, device_info):
    """Test humidity sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 1000)
    assert_state(hass, device_info, '10.0', '%')


async def async_test_temperature(hass, device_info):
    """Test temperature sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 2900)
    assert_state(hass, device_info, '29.0', '°C')


async def async_test_pressure(hass, device_info):
    """Test pressure sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 1000)
    assert_state(hass, device_info, '1000', 'hPa')


async def async_test_illuminance(hass, device_info):
    """Test illuminance sensor."""
    await send_attribute_report(hass, device_info["cluster"], 0, 10)
    assert_state(hass, device_info, '10', 'lx')


async def async_test_metering(hass, device_info):
    """Test metering sensor."""
    await send_attribute_report(hass, device_info["cluster"], 1024, 10)
    assert_state(hass, device_info, '10', 'W')


async def async_test_electrical_measurement(hass, device_info):
    """Test electrical measurement sensor."""
    await send_attribute_report(hass, device_info["cluster"], 1291, 100)
    assert_state(hass, device_info, '10.0', 'W')


async def send_attribute_report(hass, cluster, attrid, value):
    """Cause the sensor to receive an attribute report from the network."""
    attr = make_attribute(attrid, value)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()


def assert_state(hass, device_info, state, unit_of_measurement):
    """Check that the state is what is expected."""
    hass_state = hass.states.get(device_info["entity_id"])
    assert hass_state.state == state
    assert hass_state.attributes.get('unit_of_measurement') == \
        unit_of_measurement
