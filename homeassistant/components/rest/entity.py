"""The base entity for the rest component."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import RestData


class RestEntity(Entity):
    """A class for entities using DataUpdateCoordinator or rest data directly."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any] | None,
        rest: RestData,
        resource_template: Template | None,
        force_update: bool,
    ) -> None:
        """Create the entity that may have a coordinator."""
        self._coordinator = coordinator
        self.rest = rest
        self._resource_template = resource_template
        self._attr_should_poll = not coordinator
        self._attr_force_update = force_update

    @property
    def available(self) -> bool:
        """Return the availability of this sensor."""
        if self._coordinator and not self._coordinator.last_update_success:
            return False
        return self.rest.data is not None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_from_rest_data()
        if self._coordinator:
            self.async_on_remove(
                self._coordinator.async_add_listener(self._handle_coordinator_update)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_rest_data()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from REST API and update the state."""
        if self._coordinator:
            await self._coordinator.async_request_refresh()
            return

        if self._resource_template is not None:
            self.rest.set_url(self._resource_template.async_render(parse_result=False))
        await self.rest.async_update()
        self._update_from_rest_data()

    @abstractmethod
    def _update_from_rest_data(self) -> None:
        """Update state from the rest data."""
