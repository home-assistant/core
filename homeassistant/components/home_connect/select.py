"""Provides a select platform for Home Connect."""

import contextlib
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeConnectConfigEntry, get_dict_from_home_connect_error
from .api import HomeConnectDevice
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_SELECTED_PROGRAM,
    DOMAIN,
    PROGRAMS_TRANSLATION_KEYS_MAP,
    SVE_TRANSLATION_PLACEHOLDER_PROGRAM,
    TRANSLATION_KEYS_PROGRAMS_MAP,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key=BSH_ACTIVE_PROGRAM,
        translation_key="active_program",
    ),
    SelectEntityDescription(
        key=BSH_SELECTED_PROGRAM,
        translation_key="selected_program",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""

    def get_entities() -> list[HomeConnectProgramSelectEntity]:
        """Get a list of entities."""
        entities: list[HomeConnectProgramSelectEntity] = []
        programs_not_found = set()
        for device in entry.runtime_data.devices:
            if device.appliance.type in APPLIANCES_WITH_PROGRAMS:
                with contextlib.suppress(HomeConnectError):
                    programs = device.appliance.get_programs_available()
                    if programs:
                        for program in programs:
                            if program not in PROGRAMS_TRANSLATION_KEYS_MAP:
                                programs.remove(program)
                                if program not in programs_not_found:
                                    _LOGGER.info(
                                        'The program "%s" is not part of the official Home Connect API specification',
                                        program,
                                    )
                                    programs_not_found.add(program)
                        entities.extend(
                            HomeConnectProgramSelectEntity(device, programs, desc)
                            for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
                        )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    def __init__(
        self,
        device: HomeConnectDevice,
        programs: list[str],
        desc: SelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            desc,
        )
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program] for program in programs
        ]
        self.start_on_select = desc.key == BSH_ACTIVE_PROGRAM

    async def async_update(self) -> None:
        """Update the program selection status."""
        program = self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE)
        if not program:
            program_translation_key = None
        elif not (
            program_translation_key := PROGRAMS_TRANSLATION_KEYS_MAP.get(program)
        ):
            _LOGGER.debug(
                'The program "%s" is not part of the official Home Connect API specification',
                program,
            )
        self._attr_current_option = program_translation_key
        _LOGGER.debug("Updated, new program: %s", self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        bsh_key = TRANSLATION_KEYS_PROGRAMS_MAP[option]
        _LOGGER.debug(
            "Starting program: %s" if self.start_on_select else "Selecting program: %s",
            bsh_key,
        )
        if self.start_on_select:
            target = self.device.appliance.start_program
        else:
            target = self.device.appliance.select_program
        try:
            await self.hass.async_add_executor_job(target, bsh_key)
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
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: bsh_key,
                },
            ) from err
        self.async_entity_update()
