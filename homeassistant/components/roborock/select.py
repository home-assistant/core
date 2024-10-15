"""Support for Roborock select."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from roborock.containers import Status
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RoborockConfigEntry
from .const import MAP_SLEEP
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1


@dataclass(frozen=True, kw_only=True)
class RoborockSelectDescription(SelectEntityDescription):
    """Class to describe a Roborock select entity."""

    # The command that the select entity will send to the api.
    api_command: RoborockCommand
    # Gets the current value of the select entity.
    value_fn: Callable[[Status], str | None]
    # Gets all options of the select entity.
    options_lambda: Callable[[Status], list[str] | None]
    # Takes the value from the select entity and converts it for the api.
    parameter_lambda: Callable[[str, Status], list[int]]

    protocol_listener: RoborockDataProtocol | None = None


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda data: data.water_box_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.water_box_mode.keys()
        if data.water_box_mode is not None
        else None,
        parameter_lambda=lambda key, status: [status.get_mop_intensity_code(key)],
        protocol_listener=RoborockDataProtocol.WATER_BOX_MODE,
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.mop_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.mop_mode.keys()
        if data.mop_mode is not None
        else None,
        parameter_lambda=lambda key, status: [status.get_mop_mode_code(key)],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""

    async_add_entities(
        RoborockSelectEntity(coordinator, description, options)
        for coordinator in config_entry.runtime_data.v1
        for description in SELECT_DESCRIPTIONS
        if (
            options := description.options_lambda(
                coordinator.roborock_device_info.props.status
            )
        )
        is not None
    )
    async_add_entities(
        RoborockCurrentMapSelectEntity(
            f"selected_map_{coordinator.duid_slug}", coordinator
        )
        for coordinator in config_entry.runtime_data.v1
    )


class RoborockSelectEntity(RoborockCoordinatedEntityV1, SelectEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockSelectDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSelectDescription,
        options: list[str],
    ) -> None:
        """Create a select entity."""
        self.entity_description = entity_description
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator,
            entity_description.protocol_listener,
        )
        self._attr_options = options

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.parameter_lambda(option, self._device_status),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        return self.entity_description.value_fn(self._device_status)


class RoborockCurrentMapSelectEntity(RoborockCoordinatedEntityV1, SelectEntity):
    """A class to let you set the selected map on Roborock vacuum."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "selected_map"

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        for map_id, map_ in self.coordinator.maps.items():
            if map_.name == option:
                await self.send(
                    RoborockCommand.LOAD_MULTI_MAP,
                    [map_id],
                )
                # We need to wait after updating the map
                # so that other commands will be executed correctly.
                await asyncio.sleep(MAP_SLEEP)
                break

    @property
    def options(self) -> list[str]:
        """Gets all of the names of rooms that we are currently aware of."""
        return [roborock_map.name for roborock_map in self.coordinator.maps.values()]

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        if (current_map := self.coordinator.current_map) is not None:
            return self.coordinator.maps[current_map].name
        return None
