"""The AirVisual component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class AirVisualEntity(CoordinatorEntity):
    """Define a generic AirVisual entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._entry = entry
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError
