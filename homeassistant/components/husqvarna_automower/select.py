"""Creates a select entity for the headlight of the mower."""

import logging
from typing import cast

from aioautomower.model import HeadlightModes

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity, handle_sending_exception

_LOGGER = logging.getLogger(__name__)


HEADLIGHT_MODES: list = [
    HeadlightModes.ALWAYS_OFF.lower(),
    HeadlightModes.ALWAYS_ON.lower(),
    HeadlightModes.EVENING_AND_NIGHT.lower(),
    HeadlightModes.EVENING_ONLY.lower(),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select platform."""
    coordinator = entry.runtime_data
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

    @handle_sending_exception()
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.api.commands.set_headlight_mode(
            self.mower_id, cast(HeadlightModes, option.upper())
        )
