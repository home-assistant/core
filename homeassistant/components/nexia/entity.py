"""The nexia integration base entity."""

from homeassistant.helpers.entity import Entity


class NexiaEntity(Entity):
    """Base class for nexia entities."""

    def __init__(self, coordinator):
        """Initialize the entity."""
        super().__init__()
        self._coordinator = coordinator

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self._coordinator.async_remove_listener(self.async_write_ha_state)
