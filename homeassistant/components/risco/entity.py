"""A risco entity base class."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class RiscoEntity(CoordinatorEntity):
    """Risco entity base class."""

    def _get_data_from_coordinator(self):
        raise NotImplementedError

    def _refresh_from_coordinator(self):
        self._get_data_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._refresh_from_coordinator)
        )

    @property
    def _risco(self):
        """Return the Risco API object."""
        return self.coordinator.risco
