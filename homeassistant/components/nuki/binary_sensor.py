"""Doorsensor Support for the Nuki Lock."""

from __future__ import annotations

from pynuki.constants import STATE_DOORSENSOR_OPENED
from pynuki.device import NukiDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NukiEntryData
from .const import DOMAIN as NUKI_DOMAIN
from .entity import NukiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nuki binary sensors."""
    entry_data: NukiEntryData = hass.data[NUKI_DOMAIN][entry.entry_id]

    entities: list[NukiEntity] = []

    for lock in entry_data.locks:
        if lock.is_door_sensor_activated:
            entities.append(NukiDoorsensorEntity(entry_data.coordinator, lock))
        entities.append(NukiBatteryCriticalEntity(entry_data.coordinator, lock))
        entities.append(NukiBatteryChargingEntity(entry_data.coordinator, lock))

    for opener in entry_data.openers:
        entities.append(NukiRingactionEntity(entry_data.coordinator, opener))
        entities.append(NukiBatteryCriticalEntity(entry_data.coordinator, opener))

    async_add_entities(entities)


class NukiDoorsensorEntity(NukiEntity[NukiDevice], BinarySensorEntity):
    """Representation of a Nuki Lock Doorsensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_doorsensor"

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


class NukiRingactionEntity(NukiEntity[NukiDevice], BinarySensorEntity):
    """Representation of a Nuki Opener Ringaction."""

    _attr_has_entity_name = True
    _attr_translation_key = "ring_action"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_ringaction"

    @property
    def is_on(self) -> bool:
        """Return the value of the ring action state."""
        return self._nuki_device.ring_action_state


class NukiBatteryCriticalEntity(NukiEntity[NukiDevice], BinarySensorEntity):
    """Representation of Nuki Battery Critical."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_battery_critical"

    @property
    def is_on(self) -> bool:
        """Return the value of the battery critical."""
        return self._nuki_device.battery_critical


class NukiBatteryChargingEntity(NukiEntity[NukiDevice], BinarySensorEntity):
    """Representation of a Nuki Battery charging."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._nuki_device.nuki_id}_battery_charging"

    @property
    def is_on(self) -> bool:
        """Return the value of the battery charging."""
        return self._nuki_device.battery_charging
