"""Support for Roborock button."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import itertools
import logging
from typing import Any

from roborock.devices.traits.v1.consumeable import ConsumableAttribute
from roborock.devices.traits.v1.routines import RoutinesTrait
from roborock.exceptions import RoborockException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockEntity, RoborockEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockButtonDescription(ButtonEntityDescription):
    """Describes a Roborock button entity."""

    attribute: ConsumableAttribute


CONSUMABLE_BUTTON_DESCRIPTIONS = [
    RoborockButtonDescription(
        key="reset_sensor_consumable",
        translation_key="reset_sensor_consumable",
        attribute=ConsumableAttribute.SENSOR_DIRTY_TIME,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_air_filter_consumable",
        translation_key="reset_air_filter_consumable",
        attribute=ConsumableAttribute.FILTER_WORK_TIME,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_side_brush_consumable",
        translation_key="reset_side_brush_consumable",
        attribute=ConsumableAttribute.SIDE_BRUSH_WORK_TIME,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockButtonDescription(
        key="reset_main_brush_consumable",
        translation_key="reset_main_brush_consumable",
        attribute=ConsumableAttribute.MAIN_BRUSH_WORK_TIME,
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
    _LOGGER.debug("Setting up Roborock button platform")
    routines_lists = await asyncio.gather(
        *[
            routines_trait.get_routines()
            for coordinator in config_entry.runtime_data.v1
            if (routines_trait := coordinator.properties_api.routines) is not None
        ],
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
                    routines_trait=routines_trait,
                )
                for coordinator, routines in zip(
                    config_entry.runtime_data.v1, routines_lists, strict=True
                )
                if (routines_trait := coordinator.properties_api.routines) is not None
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
            api=coordinator.properties_api.command,
        )
        self.entity_description = entity_description
        self._consumable = coordinator.properties_api.consumables

    async def async_press(self) -> None:
        """Press the button."""
        _LOGGER.debug("Pressing button %s", self._consumable)
        try:
            await self._consumable.reset_consumable(self.entity_description.attribute)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "RESET_CONSUMABLE",
                },
            ) from err


class RoborockRoutineButtonEntity(RoborockEntity, ButtonEntity):
    """A class to define Roborock routines button entities."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: ButtonEntityDescription,
        routines_trait: RoutinesTrait,
    ) -> None:
        """Create a button entity."""
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.device_info,
        )
        self._routine_id = int(entity_description.key)
        self._routines_trait = routines_trait
        self.entity_description = entity_description

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        try:
            await self._routines_trait.execute_routine(self._routine_id)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "execute_scene",
                },
            ) from err
