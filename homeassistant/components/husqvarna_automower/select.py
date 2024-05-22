"""Creates a select entity for the headlight of the mower."""

import logging
from typing import cast

from aioautomower.exceptions import ApiException
from aioautomower.model import HeadlightModes

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity

_LOGGER = logging.getLogger(__name__)


HEADLIGHT_MODES: list = [
    HeadlightModes.ALWAYS_OFF.lower(),
    HeadlightModes.ALWAYS_ON.lower(),
    HeadlightModes.EVENING_AND_NIGHT.lower(),
    HeadlightModes.EVENING_ONLY.lower(),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerSelectEntity(mower_id, coordinator)
        for mower_id in coordinator.data
        if coordinator.data[mower_id].capabilities.headlights
    )


class AutomowerSelectEntity(AutomowerControlEntity, SelectEntity):
    """Defining the headlight mode entity."""

    _attr_options = HEADLIGHT_MODES
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "headlight_mode"

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up select platform."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = f"{mower_id}_headlight_mode"

    @property
    def current_option(self) -> str:
        """Return the current option for the entity."""
        return cast(
            HeadlightModes, self.mower_attributes.settings.headlight.mode
        ).lower()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.coordinator.api.commands.set_headlight_mode(
                self.mower_id, cast(HeadlightModes, option.upper())
            )
        except ApiException as exception:
            raise HomeAssistantError(
                f"Command couldn't be sent to the command queue: {exception}"
            ) from exception
