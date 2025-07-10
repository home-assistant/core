"""Creates a select entity for the headlight of the mower."""

import logging
from typing import cast

from aioautomower.model import HeadlightModes

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity, handle_sending_exception

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

HEADLIGHT_MODES: list = [
    HeadlightModes.ALWAYS_OFF,
    HeadlightModes.ALWAYS_ON,
    HeadlightModes.EVENING_AND_NIGHT,
    HeadlightModes.EVENING_ONLY,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerSelectEntity(mower_id, coordinator)
            for mower_id in mower_ids
            if coordinator.data[mower_id].capabilities.headlights
        )

    _async_add_new_devices(set(coordinator.data))

    coordinator.new_devices_callbacks.append(_async_add_new_devices)


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
        return cast(HeadlightModes, self.mower_attributes.settings.headlight.mode)

    @handle_sending_exception()
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.api.commands.set_headlight_mode(
            self.mower_id, HeadlightModes(option)
        )
