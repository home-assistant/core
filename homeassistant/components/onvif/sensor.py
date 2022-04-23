"""Support for ONVIF binary sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ONVIFBaseEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a ONVIF binary sensor."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    entities = {
        event.uid: ONVIFSensor(event.uid, device)
        for event in device.events.get_platform("sensor")
    }

    async_add_entities(entities.values())

    @callback
    def async_check_entities():
        """Check if we have added an entity for the event."""
        new_entities = []
        for event in device.events.get_platform("sensor"):
            if event.uid not in entities:
                entities[event.uid] = ONVIFSensor(event.uid, device)
                new_entities.append(entities[event.uid])
        async_add_entities(new_entities)

    device.events.async_add_listener(async_check_entities)

    return True


class ONVIFSensor(ONVIFBaseEntity, SensorEntity):
    """Representation of a ONVIF sensor event."""

    _attr_should_poll = False

    def __init__(self, uid, device):
        """Initialize the ONVIF binary sensor."""
        event = device.events.get_uid(uid)
        self._attr_device_class = event.device_class
        self._attr_entity_category = event.entity_category
        self._attr_entity_registry_enabled_default = event.entity_enabled
        self._attr_name = event.name
        self._attr_native_unit_of_measurement = event.unit_of_measurement
        self._attr_native_value = event.value
        self._attr_unique_id = uid

        super().__init__(device)

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.device.events.async_add_listener(self.async_write_ha_state)
        )
