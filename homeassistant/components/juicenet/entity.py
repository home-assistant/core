"""Adapter to wrap the pyjuicenet api for home assistant."""

from homeassistant.components.juicenet.const import DOMAIN
from homeassistant.helpers.entity import Entity


class JuiceNetDevice(Entity):
    """Represent a base JuiceNet device."""

    def __init__(self, device, sensor_type, coordinator):
        """Initialise the sensor."""
        self.device = device
        self.type = sensor_type
        self.coordinator = coordinator

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device.id}-{self.type}"

    @property
    def device_info(self):
        """Return device information about this JuiceNet Device."""
        return {
            "identifiers": {(DOMAIN, self.device.id)},
            "name": self.device.name,
            "manufacturer": "JuiceNet",
        }
