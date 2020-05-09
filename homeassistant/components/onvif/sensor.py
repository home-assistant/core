"""Support for ONVIF binary sensors."""
from typing import Optional, Union

from homeassistant.core import callback

from .base import ONVIFBaseEntity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a ONVIF binary sensor."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    entities = {
        event.idx: ONVIFSensor(event.idx, device)
        for event in device.events.get_platform("sensor")
    }

    async_add_entities(entities.values())

    @callback
    def async_check_entities():
        """Check if we have added an entity for the event."""
        new_entities = []
        for event in device.events.get_platform("sensor"):
            if event.idx not in entities:
                entities[event.idx] = ONVIFSensor(event.idx, device)
                new_entities.append(entities[event.idx])
        async_add_entities(new_entities)

    device.events.async_add_listener(async_check_entities)

    return True


class ONVIFSensor(ONVIFBaseEntity):
    """Representation of a ONVIF sensor event."""

    def __init__(self, idx, device):
        """Initialize the ONVIF binary sensor."""
        self.idx = idx

        super().__init__(device)

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the entity."""
        return self.device.events.get(self.idx).value

    @property
    def name(self):
        """Return the name of the event."""
        return self.device.events.get(self.idx).name

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self.device.events.get(self.idx).device_class

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return self.device.events.get(self.idx).unit_of_measurement

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.idx

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
