"""Support for Roborock select."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from roborock.code_mappings import RoborockDockDustCollectionModeCode
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import DeviceProp, RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MAP_SLEEP
from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockCoordinatedEntityV1

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockSelectDescription(SelectEntityDescription):
    """Class to describe a Roborock select entity."""

    # The command that the select entity will send to the api.
    api_command: RoborockCommand
    # Gets the current value of the select entity.
    value_fn: Callable[[DeviceProp], str | None]
    # Gets all options of the select entity.
    options_lambda: Callable[[DeviceProp], list[str] | None]
    # Takes the value from the select entity and converts it for the api.
    parameter_lambda: Callable[[str, DeviceProp], list[int]]

    protocol_listener: RoborockDataProtocol | None = None
    # If it is a dock entity
    is_dock_entity: bool = False


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda data: data.status.water_box_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.status.water_box_mode.keys()
        if data.status.water_box_mode is not None
        else None,
        parameter_lambda=lambda key, prop: [prop.status.get_mop_intensity_code(key)],
        protocol_listener=RoborockDataProtocol.WATER_BOX_MODE,
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.status.mop_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.status.mop_mode.keys()
        if data.status.mop_mode is not None
        else None,
        parameter_lambda=lambda key, prop: [prop.status.get_mop_mode_code(key)],
    ),
    RoborockSelectDescription(
        key="dust_collection_mode",
        translation_key="dust_collection_mode",
        api_command=RoborockCommand.SET_DUST_COLLECTION_MODE,
        value_fn=lambda data: data.dust_collection_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: RoborockDockDustCollectionModeCode.keys()
        if data.dust_collection_mode_name is not None
        else None,
        parameter_lambda=lambda key, _: [
            RoborockDockDustCollectionModeCode.as_dict().get(key)
        ],
        is_dock_entity=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""

    async_add_entities(
        RoborockSelectEntity(coordinator, description, options)
        for coordinator in config_entry.runtime_data.v1
        for description in SELECT_DESCRIPTIONS
        if (
            options := description.options_lambda(
                coordinator.roborock_device_info.props
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
            is_dock_entity=entity_description.is_dock_entity,
        )
        self._attr_options = options

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.parameter_lambda(option, self.coordinator.data),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device props."""
        return self.entity_description.value_fn(self.coordinator.data)


class RoborockCurrentMapSelectEntity(RoborockCoordinatedEntityV1, SelectEntity):
    """A class to let you set the selected map on Roborock vacuum."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "selected_map"

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        for map_id, map_ in self.coordinator.maps.items():
            if map_.name == option:
                await self._send_command(
                    RoborockCommand.LOAD_MULTI_MAP,
                    self.api,
                    [map_id],
                )
                # Update the current map id manually so that nothing gets broken
                # if another service hits the api.
                self.coordinator.current_map = map_id
                # We need to wait after updating the map
                # so that other commands will be executed correctly.
                await asyncio.sleep(MAP_SLEEP)
                await self.coordinator.async_refresh()
                break

    @property
    def options(self) -> list[str]:
        """Gets all of the names of rooms that we are currently aware of."""
        return [roborock_map.name for roborock_map in self.coordinator.maps.values()]

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        if (
            (current_map := self.coordinator.current_map) is not None
            and current_map in self.coordinator.maps
        ):  # 63 means it is searching for a map.
            return self.coordinator.maps[current_map].name
        return None
