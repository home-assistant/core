"""Doorsensor Support for the Nuki Lock."""
from __future__ import annotations

from pynuki.constants import STATE_DOORSENSOR_OPENED
from pynuki.device import NukiDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NukiCoordinator, NukiEntity
from .const import ATTR_NUKI_ID, DATA_COORDINATOR, DATA_LOCKS, DOMAIN as NUKI_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nuki lock binary sensor."""
    data = hass.data[NUKI_DOMAIN][entry.entry_id]
    coordinator: NukiCoordinator = data[DATA_COORDINATOR]

    entities = []

    for lock in data[DATA_LOCKS]:
        if lock.is_door_sensor_activated:
            entities.extend([NukiDoorsensorEntity(coordinator, lock)])

    async_add_entities(entities)


class NukiDoorsensorEntity(NukiEntity[NukiDevice], BinarySensorEntity):
    """Representation of a Nuki Lock Doorsensor."""

    _attr_has_entity_name = True
    _attr_name = "Door sensor"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_doorsensor"

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_NUKI_ID: self._nuki_device.nuki_id,
        }
        return data

    @property
    def available(self) -> bool:
        """Return true if door sensor is present and activated."""
        return super().available and self._nuki_device.is_door_sensor_activated

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
