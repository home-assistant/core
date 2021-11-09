"""Support for ONVIF binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from .base import ONVIFBaseEntity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a ONVIF binary sensor."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    entities = {
        event.uid: ONVIFBinarySensor(event.uid, device)
        for event in device.events.get_platform("binary_sensor")
    }

    async_add_entities(entities.values())

    @callback
    def async_check_entities():
        """Check if we have added an entity for the event."""
        new_entities = []
        for event in device.events.get_platform("binary_sensor"):
            if event.uid not in entities:
                entities[event.uid] = ONVIFBinarySensor(event.uid, device)
                new_entities.append(entities[event.uid])
        async_add_entities(new_entities)

    device.events.async_add_listener(async_check_entities)

    return True


class ONVIFBinarySensor(ONVIFBaseEntity, BinarySensorEntity):
    """Representation of a binary ONVIF event."""

    def __init__(self, uid, device):
        """Initialize the ONVIF binary sensor."""
        ONVIFBaseEntity.__init__(self, device)
        BinarySensorEntity.__init__(self)

        self.uid = uid

    @property
    def is_on(self) -> bool:
        """Return true if event is active."""
        return self.device.events.get_uid(self.uid).value

    @property
    def name(self) -> str:
        """Return the name of the event."""
        return self.device.events.get_uid(self.uid).name

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self.device.events.get_uid(self.uid).device_class

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.uid

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.device.events.get_uid(self.uid).entity_enabled

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.device.events.async_add_listener(self.async_write_ha_state)
        )
