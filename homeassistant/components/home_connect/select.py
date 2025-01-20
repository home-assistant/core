"""Provides a select platform for Home Connect."""

import contextlib
import logging
from typing import cast

from aiohomeconnect.model import Event, EventKey, ProgramKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import EnumerateAvailableProgram

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

_LOGGER = logging.getLogger(__name__)

TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program.value): cast(ProgramKey, program)
    for program in ProgramKey
    if program != ProgramKey.UNKNOWN
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}

PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        translation_key="active_program",
    ),
    SelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        translation_key="selected_program",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""

    async def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[HomeConnectProgramSelectEntity]:
        """Get a list of entities."""
        entities: list[HomeConnectProgramSelectEntity] = []
        if appliance.info.type in APPLIANCES_WITH_PROGRAMS:
            with contextlib.suppress(HomeConnectError):
                programs = (
                    await entry.runtime_data.client.get_available_programs(
                        appliance.info.ha_id
                    )
                ).programs
                entities.extend(
                    HomeConnectProgramSelectEntity(
                        entry.runtime_data, appliance, programs, desc
                    )
                    for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
                )
        return entities

    entities = [
        entity
        for appliance in entry.runtime_data.data.values()
        for entity in await get_entities_for_appliance(appliance)
    ]
    async_add_entities(entities, True)


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        programs: list[EnumerateAvailableProgram],
        desc: SelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
        )
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program.key]
            for program in programs
            if program.key != ProgramKey.UNKNOWN
        ]
        self.start_on_select = desc.key == EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM
        self._attr_current_option = None

    async def _async_event_update_listener(self, event: Event) -> None:
        """Update the program selection status when an event for the entity is received."""
        self.set_native_value(ProgramKey(cast(str, event.value)))
        self.async_write_ha_state()

    def set_native_value(self, program_key: ProgramKey) -> None:
        """Set the value of the entity."""
        self._attr_current_option = PROGRAMS_TRANSLATION_KEYS_MAP.get(program_key)
        _LOGGER.debug("Updated, new program: %s", self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        program_key = TRANSLATION_KEYS_PROGRAMS_MAP[option]
        _LOGGER.debug(
            "Starting program: %s" if self.start_on_select else "Selecting program: %s",
            program_key,
        )
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
