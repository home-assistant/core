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
        await _async_setup_remote(hass, config, async_add_devices,
                                  discovery_info)


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

    sensor = BinarySensor(device_class, **discovery_info)
    async_add_devices([sensor], update_before_add=True)


async def _async_setup_remote(hass, config, async_add_devices, discovery_info):

    async def safe(coro):
        """Run coro, catching ZigBee delivery errors, and ignoring them."""
        import zigpy.exceptions
        try:
            await coro
        except zigpy.exceptions.DeliveryError as exc:
            _LOGGER.warning("Ignoring error during setup: %s", exc)

    if discovery_info['new_join']:
        from zigpy.zcl.clusters.general import OnOff, LevelControl
        out_clusters = discovery_info['out_clusters']
        if OnOff.cluster_id in out_clusters:
            cluster = out_clusters[OnOff.cluster_id]
            await safe(cluster.bind())
            await safe(cluster.configure_reporting(0, 0, 600, 1))
        if LevelControl.cluster_id in out_clusters:
            cluster = out_clusters[LevelControl.cluster_id]
            await safe(cluster.bind())
            await safe(cluster.configure_reporting(0, 1, 600, 1))

    sensor = Switch(**discovery_info)
    async_add_devices([sensor], update_before_add=True)


class BinarySensor(zha.Entity, BinarySensorDevice):
    """The ZHA Binary Sensor."""

    _domain = DOMAIN

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
        from zigpy.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]

    @property
    def should_poll(self) -> bool:
        """Let zha handle polling."""
        return False

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._state == 'unknown':
            return False
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            self._state = args[0] & 3
            _LOGGER.debug("Updated alarm state: %s", self._state)
            self.async_schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            res = self._ias_zone_cluster.enroll_response(0, 0)
            self.hass.async_add_job(res)

    async def async_update(self):
        """Retrieve latest state."""
        from bellows.types.basic import uint16_t

        result = await zha.safe_read(self._endpoint.ias_zone,
                                     ['zone_status'])
        state = result.get('zone_status', self._state)
        if isinstance(state, (int, uint16_t)):
            self._state = result.get('zone_status', self._state) & 3


class Switch(zha.Entity, BinarySensorDevice):
    """ZHA switch/remote controller/button."""

    _domain = DOMAIN

    class OnOffListener:
        """Listener for the OnOff ZigBee cluster."""

        def __init__(self, entity):
            """Initialize OnOffListener."""
            self._entity = entity

        def cluster_command(self, tsn, command_id, args):
            """Handle commands received to this cluster."""
            if command_id in (0x0000, 0x0040):
                self._entity.set_state(False)
            elif command_id in (0x0001, 0x0041, 0x0042):
                self._entity.set_state(True)
            elif command_id == 0x0002:
                self._entity.set_state(not self._entity.is_on)

        def attribute_updated(self, attrid, value):
            """Handle attribute updates on this cluster."""
            if attrid == 0:
                self._entity.set_state(value)

        def zdo_command(self, *args, **kwargs):
            """Handle ZDO commands on this cluster."""
            pass

    class LevelListener:
        """Listener for the LevelControl ZigBee cluster."""

        def __init__(self, entity):
            """Initialize LevelListener."""
            self._entity = entity

        def cluster_command(self, tsn, command_id, args):
            """Handle commands received to this cluster."""
            if command_id in (0x0000, 0x0004):  # move_to_level, -with_on_off
                self._entity.set_level(args[0])
            elif command_id in (0x0001, 0x0005):  # move, -with_on_off
                # We should dim slowly -- for now, just step once
                rate = args[1]
                if args[0] == 0xff:
                    rate = 10  # Should read default move rate
                self._entity.move_level(-rate if args[0] else rate)
            elif command_id == 0x0002:  # step
                # Step (technically shouldn't change on/off)
                self._entity.move_level(-args[1] if args[0] else args[1])

        def attribute_update(self, attrid, value):
            """Handle attribute updates on this cluster."""
            if attrid == 0:
                self._entity.set_level(value)

        def zdo_command(self, *args, **kwargs):
            """Handle ZDO commands on this cluster."""
            pass

    def __init__(self, **kwargs):
        """Initialize Switch."""
        super().__init__(**kwargs)
        self._state = True
        self._level = 255
        from zigpy.zcl.clusters import general
        self._out_listeners = {
            general.OnOff.cluster_id: self.OnOffListener(self),
            general.LevelControl.cluster_id: self.LevelListener(self),
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {'level': self._state and self._level or 0}

    def move_level(self, change):
        """Increment the level, setting state if appropriate."""
        if not self._state and change > 0:
            self._level = 0
        self._level = min(255, max(0, self._level + change))
        self._state = bool(self._level)
        self.async_schedule_update_ha_state()

    def set_level(self, level):
        """Set the level, setting state if appropriate."""
        self._level = level
        self._state = bool(self._level)
        self.async_schedule_update_ha_state()

    def set_state(self, state):
        """Set the state."""
        self._state = state
        if self._level == 0:
            self._level = 255
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        from zigpy.zcl.clusters.general import OnOff
        result = await zha.safe_read(
            self._endpoint.out_clusters[OnOff.cluster_id], ['on_off'])
        self._state = result.get('on_off', self._state)
