"""Support for Roborock select."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from roborock.data import RoborockDockDustCollectionModeCode
from roborock.devices.traits.v1 import PropertiesApi
from roborock.roborock_typing import RoborockCommand

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

    api_command: RoborockCommand
    """The command that the select entity will send to the API."""

    value_fn: Callable[[PropertiesApi], str | None]
    """Function to get the current value of the select entity."""

    options_lambda: Callable[[PropertiesApi], list[str] | None]
    """Function to get all options of the select entity or returns None if not supported."""

    parameter_lambda: Callable[[str, PropertiesApi], list[int]]
    """Function to get the parameters for the api command."""

    is_dock_entity: bool = False
    """Whether this entity is for the dock."""


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda api: api.status.water_box_mode.name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: api.status.water_box_mode.keys()
        if api.status.water_box_mode is not None
        else None,
        parameter_lambda=lambda key, api: [api.status.get_mop_intensity_code(key)],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda api: api.status.mop_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: api.status.mop_mode.keys()
        if api.status.mop_mode is not None
        else None,
        parameter_lambda=lambda key, api: [api.status.get_mop_mode_code(key)],
    ),
    RoborockSelectDescription(
        key="dust_collection_mode",
        translation_key="dust_collection_mode",
        api_command=RoborockCommand.SET_DUST_COLLECTION_MODE,
        value_fn=lambda api: api.dust_collection_mode.mode.name,  # type: ignore[attr-defined]
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: RoborockDockDustCollectionModeCode.keys()
        if api.dust_collection_mode is not None
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
        if (options := description.options_lambda(coordinator.properties_api))
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
            is_dock_entity=entity_description.is_dock_entity,
        )
        self._attr_options = options

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.parameter_lambda(
                option, self.coordinator.properties_api
            ),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device props."""
        return self.entity_description.value_fn(self.coordinator.properties_api)


class RoborockCurrentMapSelectEntity(RoborockCoordinatedEntityV1, SelectEntity):
    """A class to let you set the selected map on Roborock vacuum."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "selected_map"

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        maps_trait = self.coordinator.properties_api.maps
        for map_id, map_ in self.coordinator.maps.items():
            if map_.name == option:
                await maps_trait.set_current_map(map_id)
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
