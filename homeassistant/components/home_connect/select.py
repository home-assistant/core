"""Provides a select platform for Home Connect."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import EventKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import Execution

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    AVAILABLE_MAPS_ENUM,
    DOMAIN,
    PROGRAMS_TRANSLATION_KEYS_MAP,
    SVE_TRANSLATION_KEY_SET_SETTING,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_PROGRAM,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
    TRANSLATION_KEYS_PROGRAMS_MAP,
)
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import bsh_key_to_translation_key, get_dict_from_home_connect_error

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
    """Entity Description class for settings that have enumeration values."""

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
            if appliance.info.type in APPLIANCES_WITH_PROGRAMS
            else []
        ),
        *[
            HomeConnectSelectEntity(entry.runtime_data, appliance, desc)
            for desc in SELECT_ENTITY_DESCRIPTIONS
            if desc.key in appliance.settings
        ],
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
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program.key]
            for program in appliance.programs
            if program.key != ProgramKey.UNKNOWN
            and (
                program.constraints is None
                or program.constraints.execution in desc.allowed_executions
            )
        ]

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
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: program_key.value,
                },
            ) from err


class HomeConnectSelectEntity(HomeConnectEntity, SelectEntity):
    """Select setting class for Home Connect."""

    entity_description: HomeConnectSelectEntityDescription

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectSelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
        )
        setting = appliance.settings.get(cast(SettingKey, desc.key))
        if setting and setting.constraints and setting.constraints.allowed_values:
            self._attr_options = [
                desc.values_translation_key[option]
                for option in setting.constraints.allowed_values
                if option in desc.values_translation_key
            ]

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
                translation_key=SVE_TRANSLATION_KEY_SET_SETTING,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_KEY: self.bsh_key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: value,
                },
            ) from err

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_current_option = self.entity_description.values_translation_key.get(
            data.value
        )
