"""A risco entity base class."""
from homeassistant.helpers.entity import Entity


class RiscoEntity(Entity):
    """Risco entity base class."""

    def __init__(self, coordinator):
        """Init the instance."""
        self._coordinator = coordinator

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    def _get_data_from_coordinator(self):
        raise NotImplementedError

    def _refresh_from_coordinator(self):
        self._get_data_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._refresh_from_coordinator)
        )

    @property
    def _risco(self):
        """Return the Risco API object."""
        return self._coordinator.risco

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()
