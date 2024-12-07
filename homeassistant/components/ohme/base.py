"""Base class for entities."""

from homeassistant.helpers.entity import Entity
from homeassistant.core import callback


class OhmeEntity(Entity):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True

    def __init__(self, cooordinator, hass, client):
        """Initialize the entity."""
        self.coordinator = cooordinator
        self._hass = hass
        self._client = client

        self._attributes = {}
        self._last_updated = None
        self._state = None

        self._attr_device_info = client.get_device_info()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update, None)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return unique ID of the entity."""
        return f"{self._client.serial}_{self._attr_translation_key}"
