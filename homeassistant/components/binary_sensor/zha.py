"""
Binary sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.components import zha

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup Zigbee Home Automation binary sensors."""
    if discovery_info is None:
        return

    clusters = discovery_info['clusters']

    device_class = None
    cluster = [c for c in clusters if c.cluster_id == 0x0500][0]
    if discovery_info['new_join']:
        yield from cluster.bind()
        ieee = cluster.endpoint.device.application.ieee
        yield from cluster.write_attributes({0x10: ieee})

    success, _ = yield from cluster.read_attributes([1], allow_cache=True)
    if 1 in success:
        device_class = CLASS_MAPPING.get(success[1], None)

    sensor = BinarySensor(device_class, **discovery_info)
    async_add_devices([sensor])


class BinarySensor(zha.Entity, BinarySensorDevice):
    """ZHA Binary Sensor."""

    _domain = DOMAIN

    def __init__(self, device_class, **kwargs):
        """Initialize ZHA binary sensor."""
        self._device_class = device_class
        super().__init__(**kwargs)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._state == 'unknown':
            return self._state
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    def cluster_command(self, aps_frame, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            self._state = args[0] & 3
            _LOGGER.debug("Updated alarm state: %s", self._state)
            self.schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            self.hass.add_job(self._clusters[0x0500].command(0, 0, 0))
