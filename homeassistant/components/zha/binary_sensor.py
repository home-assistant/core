"""Binary sensors on Zigbee Home Automation networks."""
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, ON_OFF_CHANNEL,
    LEVEL_CHANNEL, ZONE_CHANNEL, SIGNAL_ATTR_UPDATED, SIGNAL_MOVE_LEVEL,
    SIGNAL_SET_LEVEL, ATTRIBUTE_CHANNEL, UNKNOWN, OPENING, ZONE, OCCUPANCY,
    ATTR_LEVEL, SENSOR_TYPE, ACCELERATION)
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

# Zigbee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}


async def get_ias_device_class(channel):
    """Get the HA device class from the channel."""
    zone_type = await channel.get_attribute_value('zone_type')
    return CLASS_MAPPING.get(zone_type)


DEVICE_CLASS_REGISTRY = {
    UNKNOWN: None,
    OPENING: OPENING,
    ZONE: get_ias_device_class,
    OCCUPANCY: OCCUPANCY,
    ACCELERATION: 'moving',
}


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
    entities = []
    for discovery_info in discovery_infos:
        entities.append(BinarySensor(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class BinarySensor(ZhaEntity, BinarySensorDevice):
    """ZHA BinarySensor."""

    _domain = DOMAIN
    _device_class = None

    def __init__(self, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_state_attributes = {}
        self._zone_channel = self.cluster_channels.get(ZONE_CHANNEL)
        self._on_off_channel = self.cluster_channels.get(ON_OFF_CHANNEL)
        self._level_channel = self.cluster_channels.get(LEVEL_CHANNEL)
        self._attr_channel = self.cluster_channels.get(ATTRIBUTE_CHANNEL)
        self._zha_sensor_type = kwargs[SENSOR_TYPE]
        self._level = None

    async def _determine_device_class(self):
        """Determine the device class for this binary sensor."""
        device_class_supplier = DEVICE_CLASS_REGISTRY.get(
            self._zha_sensor_type)
        if callable(device_class_supplier):
            channel = self.cluster_channels.get(self._zha_sensor_type)
            if channel is None:
                return None
            return await device_class_supplier(channel)
        return device_class_supplier

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        self._device_class = await self._determine_device_class()
        await super().async_added_to_hass()
        if self._level_channel:
            await self.async_accept_signal(
                self._level_channel, SIGNAL_SET_LEVEL, self.set_level)
            await self.async_accept_signal(
                self._level_channel, SIGNAL_MOVE_LEVEL, self.move_level)
        if self._on_off_channel:
            await self.async_accept_signal(
                self._on_off_channel, SIGNAL_ATTR_UPDATED,
                self.async_set_state)
        if self._zone_channel:
            await self.async_accept_signal(
                self._zone_channel, SIGNAL_ATTR_UPDATED, self.async_set_state)
        if self._attr_channel:
            await self.async_accept_signal(
                self._attr_channel, SIGNAL_ATTR_UPDATED, self.async_set_state)

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        super().async_restore_last_state(last_state)
        self._state = last_state.state == STATE_ON
        if 'level' in last_state.attributes:
            self._level = last_state.attributes['level']

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

    def async_set_state(self, state):
        """Set the state."""
        self._state = bool(state)
        self.async_schedule_update_ha_state()

    def move_level(self, change):
        """Increment the level, setting state if appropriate."""
        level = self._level or 0
        if not self._state and change > 0:
            level = 0
        self._level = min(254, max(0, level + change))
        self._state = bool(self._level)
        self.async_schedule_update_ha_state()

    def set_level(self, level):
        """Set the level, setting state if appropriate."""
        self._level = level
        self._state = bool(level)
        self.async_schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self._level_channel is not None:
            self._device_state_attributes.update({
                ATTR_LEVEL: self._state and self._level or 0
            })
        return self._device_state_attributes

    async def async_update(self):
        """Attempt to retrieve on off state from the binary sensor."""
        await super().async_update()
        if self._level_channel:
            self._level = await self._level_channel.get_attribute_value(
                'current_level')
        if self._on_off_channel:
            self._state = await self._on_off_channel.get_attribute_value(
                'on_off')
        if self._zone_channel:
            value = await self._zone_channel.get_attribute_value(
                'zone_status')
            if value is not None:
                self._state = value & 3
        if self._attr_channel:
            self._state = await self._attr_channel.get_attribute_value(
                self._attr_channel.value_attribute)
