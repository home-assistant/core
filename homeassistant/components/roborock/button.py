"""Support for Roborock button."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import itertools
from typing import Any

from roborock.roborock_typing import RoborockCommand

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockEntity, RoborockEntityV1

PARALLEL_UPDATES = 0


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
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock button platform."""
    routines_lists = await asyncio.gather(
        *[coordinator.get_routines() for coordinator in config_entry.runtime_data.v1],
    )
    async_add_entities(
        itertools.chain(
            (
                RoborockButtonEntity(
                    coordinator,
                    description,
                )
                for coordinator in config_entry.runtime_data.v1
                for description in CONSUMABLE_BUTTON_DESCRIPTIONS
                if isinstance(coordinator, RoborockDataUpdateCoordinator)
            ),
            (
                RoborockRoutineButtonEntity(
                    coordinator,
                    ButtonEntityDescription(
                        key=str(routine.id),
                        name=routine.name,
                    ),
                )
                for coordinator, routines in zip(
                    config_entry.runtime_data.v1, routines_lists, strict=True
                )
                for routine in routines
            ),
        )
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
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.device_info,
            coordinator.api,
        )
        self.entity_description = entity_description

    async def async_press(self) -> None:
        """Press the button."""
        await self.send(self.entity_description.command, self.entity_description.param)


class RoborockRoutineButtonEntity(RoborockEntity, ButtonEntity):
    """A class to define Roborock routines button entities."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: ButtonEntityDescription,
    ) -> None:
        """Create a button entity."""
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.device_info,
            coordinator.api,
        )
        self._routine_id = int(entity_description.key)
        self._coordinator = coordinator
        self.entity_description = entity_description

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        await self._coordinator.execute_routines(self._routine_id)
