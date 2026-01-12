"""Support for Roborock select."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from roborock.data import RoborockDockDustCollectionModeCode
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.maps import MapsTrait
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAP_SLEEP
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
        value_fn=lambda api: api.status.water_box_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: (
            api.status.water_box_mode.keys()
            if api.status.water_box_mode is not None
            else None
        ),
        parameter_lambda=lambda key, api: [api.status.get_mop_intensity_code(key)],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda api: api.status.mop_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: (
            api.status.mop_mode.keys() if api.status.mop_mode is not None else None
        ),
        parameter_lambda=lambda key, api: [api.status.get_mop_mode_code(key)],
    ),
    RoborockSelectDescription(
        key="dust_collection_mode",
        translation_key="dust_collection_mode",
        api_command=RoborockCommand.SET_DUST_COLLECTION_MODE,
        value_fn=lambda api: (
            mode.name if (mode := api.dust_collection_mode.mode) is not None else None  # type: ignore[union-attr]
        ),
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: (
            RoborockDockDustCollectionModeCode.keys()
            if api.dust_collection_mode is not None
            else None
        ),
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
            (options := description.options_lambda(coordinator.properties_api))
            is not None
        )
    )
    async_add_entities(
        RoborockCurrentMapSelectEntity(
            f"selected_map_{coordinator.duid_slug}", coordinator, home_trait, map_trait
        )
        for coordinator in config_entry.runtime_data.v1
        if (home_trait := coordinator.properties_api.home) is not None
        if (map_trait := coordinator.properties_api.maps) is not None
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

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        home_trait: HomeTrait,
        maps_trait: MapsTrait,
    ) -> None:
        """Create a select entity to choose the current map."""
        super().__init__(unique_id, coordinator)
        self._home_trait = home_trait
        self._maps_trait = maps_trait

    @property
    def _available_map_names(self) -> dict[int, str]:
        """Get the available maps by map id."""
        return {
            map_id: map_.name or f"Map {map_id}"
            for map_id, map_ in (self._home_trait.home_map_info or {}).items()
        }

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        for map_id, map_name in self._available_map_names.items():
            if map_name == option:
                try:
                    await self._maps_trait.set_current_map(map_id)
                except RoborockException as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="command_failed",
                        translation_placeholders={
                            "command": "load_multi_map",
                        },
                    ) from err
                # We need to wait after updating the map
                # so that other commands will be executed correctly.
                await asyncio.sleep(MAP_SLEEP)
                try:
                    await self._home_trait.refresh()
                except RoborockException as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="update_data_fail",
                    ) from err
                break

    @property
    def options(self) -> list[str]:
        """Gets all of the names of rooms that we are currently aware of."""
        return list(self._available_map_names.values())

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        if current_map_info := self._home_trait.current_map_data:
            return current_map_info.name or f"Map {current_map_info.map_flag}"
        return None
