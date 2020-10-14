"""Doorsensor Support for the Nuki Lock."""

import logging

from pynuki import STATE_DOORSENSOR_OPENED

from homeassistant.components.binary_sensor import DEVICE_CLASS_DOOR, BinarySensorEntity

from . import NukiEntity
from .const import (
    ATTR_LOCK_DOORSENSOR_STATE,
    ATTR_LOCK_DOORSENSOR_STATE_NAME,
    ATTR_NUKI_ID,
    DATA_COORDINATOR,
    DATA_LOCKS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Nuki lock binary sensor."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]

    entities = []

    for lock in hass.data[DOMAIN][entry.entry_id][DATA_LOCKS]:
        if lock.is_door_sensor_activated:
            entities.extend([NukiDoorsensorEntity(coordinator, lock)])

    async_add_entities(entities)


class NukiDoorsensorEntity(NukiEntity, BinarySensorEntity):
    """Representation of a Nuki Lock Doorsensor."""

    @property
    def name(self):
        """Return the name of the lock."""
        return self._nuki_device.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return str(self._nuki_device.nuki_id) + "-doorsensor"

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_NUKI_ID: self._nuki_device.nuki_id,
            ATTR_LOCK_DOORSENSOR_STATE: self._nuki_device.door_sensor_state,
            ATTR_LOCK_DOORSENSOR_STATE_NAME: self._nuki_device.door_sensor_state_name,
        }
        return data

    @property
    def available(self):
        """Return true if door sensor is present and activated."""
        return self._nuki_device.is_door_sensor_activated

    @property
    def door_sensor_state(self):
        """Return the state of the door sensor."""
        return self._nuki_device.door_sensor_state

    @property
    def door_sensor_state_name(self):
        """Return the state name of the door sensor."""
        return self._nuki_device.door_sensor_state_name

    @property
    def is_on(self):
        """Return true if the door is open."""
        return self.door_sensor_state == STATE_DOORSENSOR_OPENED

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_DOOR
