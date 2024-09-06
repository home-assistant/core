"""Creates a button entity for Husqvarna Automower integration."""

import logging

from aioautomower.exceptions import ApiException

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerAvailableEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AutomowerButtonEntity(mower_id, coordinator)
        for mower_id in coordinator.data
        if coordinator.data[mower_id].capabilities.can_confirm_error
    )


class AutomowerButtonEntity(AutomowerAvailableEntity, ButtonEntity):
    """Defining the AutomowerButtonEntity."""

    _attr_translation_key = "confirm_error"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up button platform."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{mower_id}_confirm_error"

    @property
    def available(self) -> bool:
        """Return True if the device and entity is available."""
        return super().available and self.mower_attributes.mower.is_error_confirmable

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.api.commands.error_confirm(self.mower_id)
        except ApiException as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_send_failed",
                translation_placeholders={"exception": str(exception)},
            ) from exception
