"""
Binary sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.components.zha import helpers
from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, REPORT_CONFIG_IMMEDIATE, ZHA_DISCOVERY_NEW)
from homeassistant.components.zha.entities import ZhaEntity
from homeassistant.const import STATE_ON
from homeassistant.components.zha.entities.listeners import (
    OnOffListener, LevelListener
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

# Zigbee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}
DEVICE_CLASS_OCCUPANCY = 'occupancy'


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation binary sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation binary sensor from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    binary_sensors = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if binary_sensors is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    binary_sensors.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA binary sensors."""
    from zigpy.zcl.clusters.general import OnOff
    from zigpy.zcl.clusters.measurement import OccupancySensing
    from zigpy.zcl.clusters.security import IasZone

    entities = []
    for discovery_info in discovery_infos:
        if IasZone.cluster_id in discovery_info['in_clusters']:
            entities.append(await _async_setup_iaszone(discovery_info))
        elif OccupancySensing.cluster_id in discovery_info['in_clusters']:
            entities.append(
                BinarySensor(DEVICE_CLASS_OCCUPANCY, **discovery_info))
        elif OnOff.cluster_id in discovery_info['out_clusters']:
            entities.append(Remote(**discovery_info))

    async_add_entities(entities, update_before_add=True)


async def _async_setup_iaszone(discovery_info):
    device_class = None
    from zigpy.zcl.clusters.security import IasZone
    cluster = discovery_info['in_clusters'][IasZone.cluster_id]

    try:
        zone_type = await cluster['zone_type']
        device_class = CLASS_MAPPING.get(zone_type, None)
    except Exception:  # pylint: disable=broad-except
        # If we fail to read from the device, use a non-specific class
        pass

    return IasZoneSensor(device_class, **discovery_info)


class IasZoneSensor(RestoreEntity, ZhaEntity, BinarySensorDevice):
    """The IasZoneSensor Binary Sensor."""

    _domain = DOMAIN

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
        from zigpy.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._state is None:
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

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if self._state is not None or old_state is None:
            return

        _LOGGER.debug("%s restoring old state: %s", self.entity_id, old_state)
        if old_state.state == STATE_ON:
            self._state = 3
        else:
            self._state = 0

    async def async_configure(self):
        """Configure IAS device."""
        await self._ias_zone_cluster.bind()
        ieee = self._ias_zone_cluster.endpoint.device.application.ieee
        await self._ias_zone_cluster.write_attributes({'cie_addr': ieee})
        _LOGGER.debug("%s: finished configuration", self.entity_id)

    async def async_update(self):
        """Retrieve latest state."""
        from zigpy.types.basic import uint16_t

        result = await helpers.safe_read(self._endpoint.ias_zone,
                                         ['zone_status'],
                                         allow_cache=False,
                                         only_cache=(not self._initialized))
        state = result.get('zone_status', self._state)
        if isinstance(state, (int, uint16_t)):
            self._state = result.get('zone_status', self._state) & 3


class Remote(RestoreEntity, ZhaEntity, BinarySensorDevice):
    """ZHA switch/remote controller/button."""

    _domain = DOMAIN

    def __init__(self, **kwargs):
        """Initialize Switch."""
        super().__init__(**kwargs)
        self._level = 0
        from zigpy.zcl.clusters import general
        self._out_listeners = {
            general.OnOff.cluster_id: OnOffListener(
                self,
                self._out_clusters[general.OnOff.cluster_id]
            )
        }

        out_clusters = kwargs.get('out_clusters')
        self._zcl_reporting = {}

        if general.LevelControl.cluster_id in out_clusters:
            self._out_listeners.update({
                general.LevelControl.cluster_id: LevelListener(
                    self,
                    out_clusters[general.LevelControl.cluster_id]
                )
            })

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        self._device_state_attributes.update({
            'level': self._state and self._level or 0
        })
        return self._device_state_attributes

    @property
    def zcl_reporting_config(self):
        """Return ZCL attribute reporting configuration."""
        return self._zcl_reporting

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

    async def async_configure(self):
        """Bind clusters."""
        from zigpy.zcl.clusters import general
        await helpers.bind_cluster(
            self.entity_id,
            self._out_clusters[general.OnOff.cluster_id]
        )
        if general.LevelControl.cluster_id in self._out_clusters:
            await helpers.bind_cluster(
                self.entity_id,
                self._out_clusters[general.LevelControl.cluster_id]
            )

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if self._state is not None or old_state is None:
            return

        _LOGGER.debug("%s restoring old state: %s", self.entity_id, old_state)
        if 'level' in old_state.attributes:
            self._level = old_state.attributes['level']
        self._state = old_state.state == STATE_ON

    async def async_update(self):
        """Retrieve latest state."""
        from zigpy.zcl.clusters.general import OnOff
        result = await helpers.safe_read(
            self._endpoint.out_clusters[OnOff.cluster_id],
            ['on_off'],
            allow_cache=False,
            only_cache=(not self._initialized)
        )
        self._state = result.get('on_off', self._state)


class BinarySensor(RestoreEntity, ZhaEntity, BinarySensorDevice):
    """ZHA switch."""

    _domain = DOMAIN
    _device_class = None
    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
        self._cluster = list(kwargs['in_clusters'].values())[0]

    def attribute_updated(self, attribute, value):
        """Handle attribute update from device."""
        _LOGGER.debug("Attribute updated: %s %s %s", self, attribute, value)
        if attribute == self.value_attribute:
            self._state = bool(value)
            self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if self._state is not None or old_state is None:
            return

        _LOGGER.debug("%s restoring old state: %s", self.entity_id, old_state)
        self._state = old_state.state == STATE_ON

    @property
    def cluster(self):
        """Zigbee cluster for this entity."""
        return self._cluster

    @property
    def zcl_reporting_config(self):
        """ZHA reporting configuration."""
        return {self.cluster: {self.value_attribute: REPORT_CONFIG_IMMEDIATE}}

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
