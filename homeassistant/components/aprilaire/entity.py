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

    def __init__(
        self, coordinator: AprilaireCoordinator, unique_id: str | None
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{unique_id}_{self.translation_key}"

        self._update_available()

    def _update_available(self):
        """Update the entity availability."""

        connected: bool = self.coordinator.data.get(
            Attribute.CONNECTED, None
        ) or self.coordinator.data.get(Attribute.RECONNECTING, None)

        stopped: bool = self.coordinator.data.get(Attribute.STOPPED, None)

        self._attr_available = connected and not stopped

    async def async_update(self) -> None:
        """Implement abstract base method."""
