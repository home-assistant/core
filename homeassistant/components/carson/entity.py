"""Base class for Carson entity."""
from . import DOMAIN


class CarsonEntityMixin:
    """Base implementation for Ring device."""

    def __init__(self, config_entry_id, carson_entity):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._config_entry_id = config_entry_id
        self._carson_entity = carson_entity

    async def async_added_to_hass(self):
        """Register Entity with config."""
        self.carson_ha_entities[self.unique_id] = self

    async def async_will_remove_from_hass(self):
        """Deregister Entity with config."""
        if self.unique_id in self.carson_ha_entities:
            del self.carson_ha_entities[self.unique_id]

    @property
    def carson_ha_entities(self):
        """Return the Ring API objects."""
        return self.hass.data[DOMAIN][self._config_entry_id]["ha_entities"]

    @property
    def should_poll(self):
        """Do not poll. Update via notification."""
        return False

    @property
    def unique_id(self):
        """Name of the device."""
        return self._carson_entity.unique_entity_id
