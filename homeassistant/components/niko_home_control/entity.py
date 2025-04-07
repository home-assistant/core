"""Base class for Niko Home Control entities."""

from abc import abstractmethod

from nhc.action import NHCAction
from nhc.controller import NHCController

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class NikoHomeControlEntity(Entity):
    """Base class for Niko Home Control entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, action: NHCAction, controller: NHCController, unique_id: str
    ) -> None:
        """Set up the Niko Home Control entity."""
        self._controller = controller
        self._action = action
        self._attr_unique_id = unique_id = f"{unique_id}-{action.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Niko",
            name=action.name,
            suggested_area=action.suggested_area,
        )
        self.update_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            self._controller.register_callback(
                self._action.id, self.async_update_callback
            )
        )

    async def async_update_callback(self, state: int) -> None:
        """Handle updates from the controller."""
        self.update_state()
        self.async_write_ha_state()

    @abstractmethod
    def update_state(self) -> None:
        """Update the state of the entity."""
