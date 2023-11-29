"""Base functionality for Aprilaire entities."""

from __future__ import annotations

import logging

from pyaprilaire.const import Attribute

from homeassistant.helpers.update_coordinator import BaseCoordinatorEntity

from .coordinator import AprilaireCoordinator

_LOGGER = logging.getLogger(__name__)


class BaseAprilaireEntity(BaseCoordinatorEntity[AprilaireCoordinator]):
    """Base for Aprilaire entities."""

    _attr_available = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AprilaireCoordinator) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info

        self._update_available()

    def _update_available(self):
        """Update the entity availability."""

        connected: bool = self.coordinator.data.get(
            Attribute.CONNECTED, None
        ) or self.coordinator.data.get(Attribute.RECONNECTING, None)

        stopped: bool = self.coordinator.data.get(Attribute.STOPPED, None)

        if stopped or not connected:
            self._attr_available = False
        else:
            self._attr_available = (
                self.coordinator.data.get(Attribute.MAC_ADDRESS, None) is not None
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return (
            self.coordinator.data[Attribute.MAC_ADDRESS].replace(":", "_")
            + "_"
            + self.translation_key
        )

    async def async_update(self) -> None:
        """Implement abstract base method."""
