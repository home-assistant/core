"""Support for Roborock button."""

from __future__ import annotations

from dataclasses import dataclass

from roborock.roborock_typing import RoborockCommand

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import RoborockCoordinators
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntityV1


@dataclass(frozen=True, kw_only=True)
class RoborockButtonDescription(ButtonEntityDescription):
    """Describes a Roborock button entity."""

    command: RoborockCommand
    param: list | dict | None


CONSUMABLE_BUTTON_DESCRIPTIONS = [
    RoborockButtonDescription(
        key="reset_sensor_consumable",
        translation_key="reset_sensor_consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["sensor_dirty_time"],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_air_filter_consumable",
        translation_key="reset_air_filter_consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["filter_work_time"],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_side_brush_consumable",
        translation_key="reset_side_brush_consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["side_brush_work_time"],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_main_brush_consumable",
        translation_key="reset_main_brush_consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["main_brush_work_time"],
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock button platform."""
    coordinators: RoborockCoordinators = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        RoborockButtonEntity(
            coordinator,
            description,
        )
        for coordinator in coordinators.v1
        for description in CONSUMABLE_BUTTON_DESCRIPTIONS
        if isinstance(coordinator, RoborockDataUpdateCoordinator)
    )


class RoborockButtonEntity(RoborockEntityV1, ButtonEntity):
    """A class to define Roborock button entities."""

    entity_description: RoborockButtonDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockButtonDescription,
    ) -> None:
        """Create a button entity."""
        super().__init__(
            f"{entity_description.key}_{slugify(coordinator.duid)}",
            coordinator.device_info,
            coordinator.api,
        )
        self.entity_description = entity_description

    async def async_press(self) -> None:
        """Press the button."""
        await self.send(self.entity_description.command, self.entity_description.param)
