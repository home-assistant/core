"""Support for Roborock button."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import itertools
import logging
from typing import Any

from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.consumeable import ConsumableAttribute
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockZeoProtocol
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
    RoborockWashingMachineUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityA01, RoborockEntity, RoborockEntityV1

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


@dataclass(frozen=True, kw_only=True)
class RoborockButtonDescriptionA01(ButtonEntityDescription):
    """Describes a Roborock A01 button entity."""

    data_protocol: RoborockZeoProtocol


ZEO_BUTTON_DESCRIPTIONS = [
    RoborockButtonDescriptionA01(
        key="start",
        data_protocol=RoborockZeoProtocol.START,
        translation_key="start",
    ),
    RoborockButtonDescriptionA01(
        key="pause",
        data_protocol=RoborockZeoProtocol.PAUSE,
        translation_key="pause",
    ),
    RoborockButtonDescriptionA01(
        key="shutdown",
        data_protocol=RoborockZeoProtocol.SHUTDOWN,
        translation_key="shutdown",
    ),
]


@dataclass(frozen=True, kw_only=True)
class RoborockDockCommandButtonDescription(ButtonEntityDescription):
    """Describes a Roborock dock command button entity."""

    api_command: RoborockCommand
    availability_fn: Callable[[PropertiesApi], bool]
    """Return True if this button should be created for the given device."""


DOCK_COMMAND_BUTTON_DESCRIPTIONS: list[RoborockDockCommandButtonDescription] = [
    RoborockDockCommandButtonDescription(
        key="dock_empty",
        translation_key="dock_empty",
        api_command=RoborockCommand.APP_START_COLLECT_DUST,
        availability_fn=lambda api: api.dust_collection_mode is not None,
        entity_registry_enabled_default=False,
    ),
    RoborockDockCommandButtonDescription(
        key="dock_wash_mop",
        translation_key="dock_wash_mop",
        api_command=RoborockCommand.APP_START_WASH,
        # wash_towel_mode being non-None is the API proxy for "has mop washing station"
        availability_fn=lambda api: api.wash_towel_mode is not None,
        entity_registry_enabled_default=False,
    ),
    RoborockDockCommandButtonDescription(
        key="dock_stop_drying",
        translation_key="dock_stop_drying",
        api_command=RoborockCommand.APP_STOP_WASH,
        availability_fn=lambda api: api.wash_towel_mode is not None,
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
            (
                RoborockButtonEntityA01(
                    coordinator,
                    description,
                )
                for coordinator in config_entry.runtime_data.a01
                if isinstance(coordinator, RoborockWashingMachineUpdateCoordinator)
                for description in ZEO_BUTTON_DESCRIPTIONS
            ),
            (
                RoborockDockCommandButtonEntity(coordinator, description)
                for coordinator in config_entry.runtime_data.v1
                for description in DOCK_COMMAND_BUTTON_DESCRIPTIONS
                if isinstance(coordinator, RoborockDataUpdateCoordinator)
                if description.availability_fn(coordinator.properties_api)
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
        try:
            await self._consumable.reset_consumable(self.entity_description.attribute)
        except RoborockException as err:
            # This error message could be improved since it is fairly low level
            # and technical. Can add a more user friendly message with the
            # name of the attribute being reset.
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
    ) -> None:
        """Create a button entity."""
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.device_info,
        )
        self._routine_id = int(entity_description.key)
        self._coordinator = coordinator
        self.entity_description = entity_description

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        await self._coordinator.execute_routines(self._routine_id)


class RoborockButtonEntityA01(RoborockCoordinatedEntityA01, ButtonEntity):
    """A class to define Roborock A01 button entities."""

    entity_description: RoborockButtonDescriptionA01

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinatorA01,
        entity_description: RoborockButtonDescriptionA01,
    ) -> None:
        """Create an A01 button entity."""
        self.entity_description = entity_description
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}", coordinator
        )

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.coordinator.api.set_value(  # type: ignore[attr-defined]
                self.entity_description.data_protocol,
                1,
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_press_failed",
            ) from err
        finally:
            await self.coordinator.async_request_refresh()


class RoborockDockCommandButtonEntity(RoborockEntityV1, ButtonEntity):
    """A class to define Roborock dock command button entities."""

    entity_description: RoborockDockCommandButtonDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockDockCommandButtonDescription,
    ) -> None:
        """Create a dock command button entity."""
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator.dock_device_info,
            api=coordinator.properties_api.command,
        )
        self.entity_description = entity_description

    async def async_press(self, **kwargs: Any) -> None:
        """Send the dock command."""
        await self.send(self.entity_description.api_command)
