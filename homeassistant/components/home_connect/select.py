"""Provides a select platform for Home Connect."""

from dataclasses import dataclass
from typing import cast

from aiohomeconnect.model import EventKey, ProgramKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import Execution

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import APPLIANCES_WITH_PROGRAMS, DOMAIN, SVE_TRANSLATION_PLACEHOLDER_PROGRAM
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import bsh_key_to_translation_key, get_dict_from_home_connect_error

TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program.value): cast(ProgramKey, program)
    for program in ProgramKey
    if program != ProgramKey.UNKNOWN
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(
    SelectEntityDescription,
):
    """Entity Description class for sensors."""

    allowed_executions: tuple[Execution, ...]


PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        translation_key="active_program",
        allowed_executions=(Execution.SELECT_AND_START, Execution.START_ONLY),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        translation_key="selected_program",
        allowed_executions=(Execution.SELECT_AND_START, Execution.SELECT_ONLY),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""

    async_add_entities(
        HomeConnectProgramSelectEntity(entry.runtime_data, appliance, desc)
        for appliance in entry.runtime_data.data.values()
        for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
        if appliance.info.type in APPLIANCES_WITH_PROGRAMS
    )


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    entity_description: HomeConnectSensorEntityDescription

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: HomeConnectSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
        )
        self.start_on_select = desc.key == EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program.key]
            for program in appliance.programs
            if program.key != ProgramKey.UNKNOWN
            and (
                program.constraints.execution in desc.allowed_executions
                if program.constraints is not None
                else True
            )
        ]
        self._attr_current_option = None

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
            if self.start_on_select:
                await self.coordinator.client.start_program(
                    self.appliance.info.ha_id, program_key=program_key
                )
            else:
                await self.coordinator.client.set_selected_program(
                    self.appliance.info.ha_id, program_key=program_key
                )
        except HomeConnectError as err:
            if self.start_on_select:
                translation_key = "start_program"
            else:
                translation_key = "select_program"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: program_key.value,
                },
            ) from err
