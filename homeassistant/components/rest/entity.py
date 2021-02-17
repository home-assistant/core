"""The base entity for the rest component."""

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class RestEntity(Entity):
    """A class for entities using DataUpdateCoordinator or rest data directly."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        name,
        device_class,
        resource_template,
        force_update,
    ) -> None:
        """Create the entity with a DataUpdateCoordinator."""
        self.coordinator = coordinator
        self._name = name
        self._device_class = device_class
        self._resource_template = resource_template
        self._force_update = force_update
        super().__init__()

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def should_poll(self) -> bool:
        """Poll only if we do noty have a coordinator."""
        return not self.coordinator

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator:
            return True
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_from_rest_data()
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_rest_data()
        self.async_write_ha_state()

    async def async_update(self):
        """Get the latest data from REST API and update the state."""
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.async_render(parse_result=False))

        if self.coordinator:
            await self.coordinator.async_request_refresh()
            return

        await self.rest.async_update()
        self._update_from_rest_data()
