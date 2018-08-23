"""
Binary sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.components import zha

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

# ZigBee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}

DEVICE_CLASS_OPENING = 'opening'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Zigbee Home Automation binary sensors."""
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    from zigpy.zcl.clusters.general import OnOff
    from zigpy.zcl.clusters.security import IasZone
    if IasZone.cluster_id in discovery_info['in_clusters']:
        await _async_setup_iaszone(hass, config, async_add_devices,
                                   discovery_info)
    elif OnOff.cluster_id in discovery_info['out_clusters']:
        await _async_setup_onoff(hass, config, async_add_devices,
                                 discovery_info, DEVICE_CLASS_OPENING)


async def _async_setup_iaszone(hass, config, async_add_devices,
                               discovery_info):
    device_class = None
    from zigpy.zcl.clusters.security import IasZone
    cluster = discovery_info['in_clusters'][IasZone.cluster_id]
    if discovery_info['new_join']:
        await cluster.bind()
        ieee = cluster.endpoint.device.application.ieee
        await cluster.write_attributes({'cie_addr': ieee})

    try:
        zone_type = await cluster['zone_type']
        device_class = CLASS_MAPPING.get(zone_type, None)
    except Exception:  # pylint: disable=broad-except
        # If we fail to read from the device, use a non-specific class
        pass

    sensor = IasZoneSensor(device_class, **discovery_info)
    async_add_devices([sensor])


async def _async_setup_onoff(hass, config, async_add_devices,
                             discovery_info, device_class):
    sensor = BinarySensor(device_class, **discovery_info)

    if discovery_info['new_join']:
        from zigpy.exceptions import ZigbeeException
        from zigpy.zcl.clusters.general import OnOff
        in_clusters = discovery_info['in_clusters']
        endpoint = discovery_info['endpoint']
        cluster = in_clusters[OnOff.cluster_id]
        attr, min_report, max_report, report_change = [0, 0, 600, 1]
        try:
            await cluster.bind()
        except ZigbeeException as ex:
            _LOGGER.debug("Failed to bind {}-{}-{}: {}".
                          format(endpoint.device.ieee, endpoint.endpoint_id,
                                 cluster.cluster_id, ex))
        try:
            await cluster.configure_reporting(attr, min_report,
                                              max_report, report_change)
        except ZigbeeException as ex:
            _LOGGER.debug(
                "Failed to configure reporting for attr {} on {}-{}-{}: {}"
                .format(attr, endpoint.device.ieee, endpoint.endpoint_id,
                        cluster.cluster_id, ex))

    async_add_devices([sensor])


class BinarySensor(zha.Entity, BinarySensorDevice):
    """ZHA Binary Sensor."""

    _domain = DOMAIN
    _device_class = None
    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        _LOGGER.debug("Attribute updated: %s %s %s", self, attribute, value)
        if attribute == self.value_attribute:
            self._state = bool(value)
            self.async_schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Let zha handle polling."""
        return False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return self._state

    @property
    def device_class(self) -> str:
        """Return device class from component DEVICE_CLASSES."""
        return self._device_class


class IasZoneSensor(BinarySensor, BinarySensorDevice):
    """The ZHA Binary Sensor."""

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(device_class, **kwargs)
        from zigpy.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            self._state = bool(args[0] & 3)
            _LOGGER.debug("Updated alarm state: %s", self._state)
            self.async_schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            res = self._ias_zone_cluster.enroll_response(0, 0)
            self.hass.async_add_job(res)
