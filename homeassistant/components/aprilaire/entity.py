"""Base functionality for Aprilaire entities."""

from __future__ import annotations

from pyaprilaire.const import Attribute

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .coordinator import AprilaireCoordinator


class BaseAprilaireEntity(CoordinatorEntity[AprilaireCoordinator], Entity):
    """Base for Aprilaire entities."""

    _attr_available = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AprilaireCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._coordinator = coordinator

        self._update_available()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        self._coordinator.logger.debug("Current data: %s", self._coordinator.data)

        self._update_available()

        self.async_write_ha_state()

    def _update_available(self):
        """Update the entity availability."""

        connected: bool = self._coordinator.data.get(
            Attribute.CONNECTED, None
        ) or self._coordinator.data.get(Attribute.RECONNECTING, None)

        stopped: bool = self._coordinator.data.get(Attribute.STOPPED, None)

        if stopped or not connected:
            self._attr_available = False
        else:
            self._attr_available = (
                self._coordinator.data.get(Attribute.MAC_ADDRESS, None) is not None
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return slugify(
            self._coordinator.data[Attribute.MAC_ADDRESS].replace(":", "_")
            + "_"
            + self.name
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""

        return self._coordinator.device_info

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "device_name": self._coordinator.device_name,
            "device_location": self._coordinator.data.get(Attribute.LOCATION),
        }
