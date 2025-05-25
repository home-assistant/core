"""Provides a select platform for Home Connect."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, cast

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import EventKey, OptionKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import Execution

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import (
    AVAILABLE_MAPS_ENUM,
    BEAN_AMOUNT_OPTIONS,
    BEAN_CONTAINER_OPTIONS,
    CLEANING_MODE_OPTIONS,
    COFFEE_MILK_RATIO_OPTIONS,
    COFFEE_TEMPERATURE_OPTIONS,
    DOMAIN,
    DRYING_TARGET_OPTIONS,
    FLOW_RATE_OPTIONS,
    HOT_WATER_TEMPERATURE_OPTIONS,
    INTENSIVE_LEVEL_OPTIONS,
    PROGRAMS_TRANSLATION_KEYS_MAP,
    SPIN_SPEED_OPTIONS,
    TEMPERATURE_OPTIONS,
    TRANSLATION_KEYS_PROGRAMS_MAP,
    VARIO_PERFECT_OPTIONS,
    VENTING_LEVEL_OPTIONS,
    WARMING_LEVEL_OPTIONS,
)
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity, HomeConnectOptionEntity, constraint_fetcher
from .utils import bsh_key_to_translation_key, get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

FUNCTIONAL_LIGHT_COLOR_TEMPERATURE_ENUM = {
    bsh_key_to_translation_key(option): option
    for option in (
        "Cooking.Hood.EnumType.ColorTemperature.custom",
        "Cooking.Hood.EnumType.ColorTemperature.warm",
        "Cooking.Hood.EnumType.ColorTemperature.warmToNeutral",
        "Cooking.Hood.EnumType.ColorTemperature.neutral",
        "Cooking.Hood.EnumType.ColorTemperature.neutralToCold",
        "Cooking.Hood.EnumType.ColorTemperature.cold",
    )
}

AMBIENT_LIGHT_COLOR_TEMPERATURE_ENUM = {
    **{
        bsh_key_to_translation_key(option): option
        for option in ("BSH.Common.EnumType.AmbientLightColor.CustomColor",)
    },
    **{
        str(option): f"BSH.Common.EnumType.AmbientLightColor.Color{option}"
        for option in range(1, 100)
    },
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectProgramSelectEntityDescription(
    SelectEntityDescription,
):
    """Entity Description class for select entities for programs."""

    allowed_executions: tuple[Execution, ...]
    set_program_fn: Callable[
        [HomeConnectClient, str, ProgramKey], Coroutine[Any, Any, None]
    ]
    error_translation_key: str


@dataclass(frozen=True, kw_only=True)
class HomeConnectSelectEntityDescription(SelectEntityDescription):
    """Entity Description class for settings and options that have enumeration values."""

    translation_key_values: dict[str, str]
    values_translation_key: dict[str, str]


PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    HomeConnectProgramSelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        translation_key="active_program",
        allowed_executions=(Execution.SELECT_AND_START, Execution.START_ONLY),
        set_program_fn=lambda client, ha_id, program_key: client.start_program(
            ha_id, program_key=program_key
        ),
        error_translation_key="start_program",
    ),
    HomeConnectProgramSelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        translation_key="selected_program",
        allowed_executions=(Execution.SELECT_AND_START, Execution.SELECT_ONLY),
        set_program_fn=lambda client, ha_id, program_key: client.set_selected_program(
            ha_id, program_key=program_key
        ),
        error_translation_key="select_program",
    ),
)

SELECT_ENTITY_DESCRIPTIONS = (
    HomeConnectSelectEntityDescription(
        key=SettingKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_CURRENT_MAP,
        translation_key="current_map",
        options=list(AVAILABLE_MAPS_ENUM),
        translation_key_values=AVAILABLE_MAPS_ENUM,
        values_translation_key={
            value: translation_key
            for translation_key, value in AVAILABLE_MAPS_ENUM.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=SettingKey.COOKING_HOOD_COLOR_TEMPERATURE,
        translation_key="functional_light_color_temperature",
        options=list(FUNCTIONAL_LIGHT_COLOR_TEMPERATURE_ENUM),
        translation_key_values=FUNCTIONAL_LIGHT_COLOR_TEMPERATURE_ENUM,
        values_translation_key={
            value: translation_key
            for translation_key, value in FUNCTIONAL_LIGHT_COLOR_TEMPERATURE_ENUM.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=SettingKey.BSH_COMMON_AMBIENT_LIGHT_COLOR,
        translation_key="ambient_light_color",
        options=list(AMBIENT_LIGHT_COLOR_TEMPERATURE_ENUM),
        translation_key_values=AMBIENT_LIGHT_COLOR_TEMPERATURE_ENUM,
        values_translation_key={
            value: translation_key
            for translation_key, value in AMBIENT_LIGHT_COLOR_TEMPERATURE_ENUM.items()
        },
    ),
)

PROGRAM_SELECT_OPTION_ENTITY_DESCRIPTIONS = (
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_REFERENCE_MAP_ID,
        translation_key="reference_map_id",
        options=list(AVAILABLE_MAPS_ENUM),
        translation_key_values=AVAILABLE_MAPS_ENUM,
        values_translation_key={
            value: translation_key
            for translation_key, value in AVAILABLE_MAPS_ENUM.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_CLEANING_MODE,
        translation_key="cleaning_mode",
        options=list(CLEANING_MODE_OPTIONS),
        translation_key_values=CLEANING_MODE_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in CLEANING_MODE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEAN_AMOUNT,
        translation_key="bean_amount",
        options=list(BEAN_AMOUNT_OPTIONS),
        translation_key_values=BEAN_AMOUNT_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in BEAN_AMOUNT_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_COFFEE_TEMPERATURE,
        translation_key="coffee_temperature",
        options=list(COFFEE_TEMPERATURE_OPTIONS),
        translation_key_values=COFFEE_TEMPERATURE_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in COFFEE_TEMPERATURE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEAN_CONTAINER_SELECTION,
        translation_key="bean_container",
        options=list(BEAN_CONTAINER_OPTIONS),
        translation_key_values=BEAN_CONTAINER_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in BEAN_CONTAINER_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_FLOW_RATE,
        translation_key="flow_rate",
        options=list(FLOW_RATE_OPTIONS),
        translation_key_values=FLOW_RATE_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in FLOW_RATE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_COFFEE_MILK_RATIO,
        translation_key="coffee_milk_ratio",
        options=list(COFFEE_MILK_RATIO_OPTIONS),
        translation_key_values=COFFEE_MILK_RATIO_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in FLOW_RATE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_HOT_WATER_TEMPERATURE,
        translation_key="hot_water_temperature",
        options=list(HOT_WATER_TEMPERATURE_OPTIONS),
        translation_key_values=HOT_WATER_TEMPERATURE_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in HOT_WATER_TEMPERATURE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.LAUNDRY_CARE_DRYER_DRYING_TARGET,
        translation_key="drying_target",
        options=list(DRYING_TARGET_OPTIONS),
        translation_key_values=DRYING_TARGET_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in DRYING_TARGET_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.COOKING_COMMON_HOOD_VENTING_LEVEL,
        translation_key="venting_level",
        options=list(VENTING_LEVEL_OPTIONS),
        translation_key_values=VENTING_LEVEL_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in VENTING_LEVEL_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.COOKING_COMMON_HOOD_INTENSIVE_LEVEL,
        translation_key="intensive_level",
        options=list(INTENSIVE_LEVEL_OPTIONS),
        translation_key_values=INTENSIVE_LEVEL_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in INTENSIVE_LEVEL_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.COOKING_OVEN_WARMING_LEVEL,
        translation_key="warming_level",
        options=list(WARMING_LEVEL_OPTIONS),
        translation_key_values=WARMING_LEVEL_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in WARMING_LEVEL_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE,
        translation_key="washer_temperature",
        options=list(TEMPERATURE_OPTIONS),
        translation_key_values=TEMPERATURE_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in TEMPERATURE_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.LAUNDRY_CARE_WASHER_SPIN_SPEED,
        translation_key="spin_speed",
        options=list(SPIN_SPEED_OPTIONS),
        translation_key_values=SPIN_SPEED_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in SPIN_SPEED_OPTIONS.items()
        },
    ),
    HomeConnectSelectEntityDescription(
        key=OptionKey.LAUNDRY_CARE_COMMON_VARIO_PERFECT,
        translation_key="vario_perfect",
        options=list(VARIO_PERFECT_OPTIONS),
        translation_key_values=VARIO_PERFECT_OPTIONS,
        values_translation_key={
            value: translation_key
            for translation_key, value in VARIO_PERFECT_OPTIONS.items()
        },
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        *(
            [
                HomeConnectProgramSelectEntity(entry.runtime_data, appliance, desc)
                for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
            ]
            if appliance.programs
            else []
        ),
        *[
            HomeConnectSelectEntity(entry.runtime_data, appliance, desc)
            for desc in SELECT_ENTITY_DESCRIPTIONS
            if desc.key in appliance.settings
        ],
    ]


def _get_option_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectOptionEntity]:
    """Get a list of entities."""
    return [
        HomeConnectSelectOptionEntity(entry.runtime_data, appliance, desc)
        for desc in PROGRAM_SELECT_OPTION_ENTITY_DESCRIPTIONS
        if desc.key in appliance.options
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
        _get_option_entities_for_appliance,
    )


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    entity_description: HomeConnectProgramSelectEntityDescription

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectProgramSelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
        )
        self.set_options()

    def set_options(self) -> None:
        """Set the options for the entity."""
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program.key]
            for program in self.appliance.programs
            if program.key != ProgramKey.UNKNOWN
            and (
                program.constraints is None
                or program.constraints.execution
                in self.entity_description.allowed_executions
            )
        ]

    @callback
    def refresh_options(self) -> None:
        """Refresh the options for the entity."""
        self.set_options()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self.refresh_options,
                (self.appliance.info.ha_id, EventKey.BSH_COMMON_APPLIANCE_CONNECTED),
            )
        )

    def update_native_value(self) -> None:
        """Set the program value."""
        event = self.appliance.events.get(cast(EventKey, self.bsh_key))
        self._attr_current_option = (
            PROGRAMS_TRANSLATION_KEYS_MAP.get(cast(ProgramKey, event.value))
            if event
            else None
        )

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        program_key = TRANSLATION_KEYS_PROGRAMS_MAP[option]
        try:
            await self.entity_description.set_program_fn(
                self.coordinator.client,
                self.appliance.info.ha_id,
                program_key,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=self.entity_description.error_translation_key,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "program": program_key.value,
                },
            ) from err


class HomeConnectSelectEntity(HomeConnectEntity, SelectEntity):
    """Select setting class for Home Connect."""

    entity_description: HomeConnectSelectEntityDescription
    _original_option_keys: set[str | None]

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectSelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._original_option_keys = set(desc.values_translation_key)
        super().__init__(
            coordinator,
            appliance,
            desc,
        )

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        value = self.entity_description.translation_key_values[option]
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=cast(SettingKey, self.bsh_key),
                value=value,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_setting_entity",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "entity_id": self.entity_id,
                    "key": self.bsh_key,
                    "value": value,
                },
            ) from err

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_current_option = self.entity_description.values_translation_key.get(
            data.value
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        await self.async_fetch_options()

    @constraint_fetcher
    async def async_fetch_options(self) -> None:
        """Fetch options from the API."""
        setting = self.appliance.settings.get(cast(SettingKey, self.bsh_key))
        if (
            not setting
            or not setting.constraints
            or not setting.constraints.allowed_values
        ):
            setting = await self.coordinator.client.get_setting(
                self.appliance.info.ha_id,
                setting_key=cast(SettingKey, self.bsh_key),
            )

        if setting and setting.constraints and setting.constraints.allowed_values:
            self._original_option_keys = set(setting.constraints.allowed_values)
            self._attr_options = [
                self.entity_description.values_translation_key[option]
                for option in self._original_option_keys
                if option is not None
                and option in self.entity_description.values_translation_key
            ]


class HomeConnectSelectOptionEntity(HomeConnectOptionEntity, SelectEntity):
    """Select option class for Home Connect."""

    entity_description: HomeConnectSelectEntityDescription
    _original_option_keys: set[str | None]

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectSelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._original_option_keys = set(desc.values_translation_key)
        super().__init__(
            coordinator,
            appliance,
            desc,
        )

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        await self.async_set_option(
            self.entity_description.translation_key_values[option]
        )

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        self._attr_current_option = (
            self.entity_description.values_translation_key.get(
                cast(str, self.option_value), None
            )
            if self.option_value is not None
            else None
        )
        if (
            (option_definition := self.appliance.options.get(self.bsh_key))
            and (option_constraints := option_definition.constraints)
            and option_constraints.allowed_values
            and self._original_option_keys != set(option_constraints.allowed_values)
        ):
            self._original_option_keys = set(option_constraints.allowed_values)
            self._attr_options = [
                self.entity_description.values_translation_key[option]
                for option in self._original_option_keys
                if option is not None
                and option in self.entity_description.values_translation_key
            ]
