"""Support for Roborock select."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from roborock import B01Props, CleanTypeMapping
from roborock.data import (
    RoborockDockDustCollectionModeCode,
    RoborockEnum,
    WaterLevelMapping,
    ZeoDetergentType,
    ZeoDryingMode,
    ZeoMode,
    ZeoProgram,
    ZeoRinse,
    ZeoSoftenerType,
    ZeoSpin,
    ZeoTemperature,
)
from roborock.devices.traits.b01 import Q7PropertiesApi
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.maps import MapsTrait
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockZeoProtocol
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAP_SLEEP
from .coordinator import (
    RoborockB01Q7UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
)
from .entity import (
    RoborockCoordinatedEntityA01,
    RoborockCoordinatedEntityB01Q7,
    RoborockCoordinatedEntityV1,
)

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True, kw_only=True)
class RoborockB01SelectDescription(SelectEntityDescription):
    """Class to describe a Roborock B01 select entity."""

    api_fn: Callable[[Q7PropertiesApi, str], Awaitable[Any]]
    """Function to call the API."""

    value_fn: Callable[[B01Props], str | None]
    """Function to get the current value of the select entity."""

    options_lambda: Callable[[Q7PropertiesApi], list[str] | None]
    """Function to get all options of the select entity or returns None if not supported."""


@dataclass(frozen=True, kw_only=True)
class RoborockSelectDescriptionA01(SelectEntityDescription):
    """Class to describe a Roborock A01 select entity."""

    # The protocol that the select entity will send to the api.
    data_protocol: RoborockZeoProtocol
    # Enum class for the select entity
    enum_class: type[RoborockEnum]


B01_SELECT_DESCRIPTIONS: list[RoborockB01SelectDescription] = [
    RoborockB01SelectDescription(
        key="water_flow",
        translation_key="water_flow",
        api_fn=lambda api, value: api.set_water_level(
            WaterLevelMapping.from_value(value)
        ),
        value_fn=lambda data: data.water.value if data.water else None,
        options_lambda=lambda _: [option.value for option in WaterLevelMapping],
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockB01SelectDescription(
        key="cleaning_mode",
        translation_key="cleaning_mode",
        api_fn=lambda api, value: api.set_mode(CleanTypeMapping.from_value(value)),
        value_fn=lambda data: data.mode.value if data.mode else None,
        options_lambda=lambda _: list(CleanTypeMapping.keys()),
        entity_category=EntityCategory.CONFIG,
    ),
]


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda api: api.status.water_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: (
            [mode.value for mode in api.status.water_mode_options]
            if api.status.water_mode_options
            else None
        ),
        parameter_lambda=lambda key, api: [
            {v: k for k, v in api.status.water_mode_mapping.items()}[key]
        ],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda api: api.status.mop_route_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda api: (
            [mode.value for mode in api.status.mop_route_options]
            if api.status.mop_route_options
            else None
        ),
        parameter_lambda=lambda key, api: [
            {v: k for k, v in api.status.mop_route_mapping.items()}[key]
        ],
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


A01_SELECT_DESCRIPTIONS: list[RoborockSelectDescriptionA01] = [
    RoborockSelectDescriptionA01(
        key="program",
        data_protocol=RoborockZeoProtocol.PROGRAM,
        translation_key="program",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoProgram,
    ),
    RoborockSelectDescriptionA01(
        key="mode",
        data_protocol=RoborockZeoProtocol.MODE,
        translation_key="mode",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoMode,
    ),
    RoborockSelectDescriptionA01(
        key="temperature",
        data_protocol=RoborockZeoProtocol.TEMP,
        translation_key="temperature",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoTemperature,
    ),
    RoborockSelectDescriptionA01(
        key="drying_mode",
        data_protocol=RoborockZeoProtocol.DRYING_MODE,
        translation_key="drying_mode",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoDryingMode,
    ),
    RoborockSelectDescriptionA01(
        key="spin_level",
        data_protocol=RoborockZeoProtocol.SPIN_LEVEL,
        translation_key="spin_level",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoSpin,
    ),
    RoborockSelectDescriptionA01(
        key="rinse_times",
        data_protocol=RoborockZeoProtocol.RINSE_TIMES,
        translation_key="rinse_times",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoRinse,
    ),
    RoborockSelectDescriptionA01(
        key="detergent_type",
        data_protocol=RoborockZeoProtocol.DETERGENT_TYPE,
        translation_key="detergent_type",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoDetergentType,
    ),
    RoborockSelectDescriptionA01(
        key="softener_type",
        data_protocol=RoborockZeoProtocol.SOFTENER_TYPE,
        translation_key="softener_type",
        entity_category=EntityCategory.CONFIG,
        enum_class=ZeoSoftenerType,
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
    async_add_entities(
        RoborockB01SelectEntity(coordinator, description, options)
        for coordinator in config_entry.runtime_data.b01_q7
        for description in B01_SELECT_DESCRIPTIONS
        if (options := description.options_lambda(coordinator.api)) is not None
    )
    async_add_entities(
        RoborockSelectEntityA01(coordinator, description)
        for coordinator in config_entry.runtime_data.a01
        for description in A01_SELECT_DESCRIPTIONS
        if description.data_protocol in coordinator.request_protocols
    )


class RoborockB01SelectEntity(RoborockCoordinatedEntityB01Q7, SelectEntity):
    """Select entity for Roborock B01 devices."""

    entity_description: RoborockB01SelectDescription
    coordinator: RoborockB01Q7UpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockB01Q7UpdateCoordinator,
        entity_description: RoborockB01SelectDescription,
        options: list[str],
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}", coordinator
        )
        self._attr_options = options

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        try:
            await self.entity_description.api_fn(self.coordinator.api, option)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": self.entity_description.key,
                },
            ) from err
        await self.coordinator.async_refresh()

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.value_fn(self.coordinator.data)


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


class RoborockSelectEntityA01(RoborockCoordinatedEntityA01, SelectEntity):
    """A class to let you set options on a Roborock A01 device."""

    entity_description: RoborockSelectDescriptionA01

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinatorA01,
        entity_description: RoborockSelectDescriptionA01,
    ) -> None:
        """Create an A01 select entity."""
        self.entity_description = entity_description
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator,
        )
        self._attr_options = list(entity_description.enum_class.keys())

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        # Get the protocol value for the selected option
        option_values = self.entity_description.enum_class.as_dict()
        if option not in option_values:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="select_option_failed",
            )
        value = option_values[option]
        try:
            await self.coordinator.api.set_value(  # type: ignore[attr-defined]
                self.entity_description.data_protocol,
                value,
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": self.entity_description.key,
                },
            ) from err

        await self.coordinator.async_request_refresh()

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from coordinator data."""
        if self.entity_description.data_protocol not in self.coordinator.data:
            return None

        current_value = self.coordinator.data[self.entity_description.data_protocol]
        if current_value is None:
            return None
        _LOGGER.debug(
            "current_value: %s for %s",
            current_value,
            self.entity_description.key,
        )
        return str(current_value)
