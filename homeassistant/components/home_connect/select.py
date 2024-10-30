"""Provides a selector for Home Connect."""

import contextlib
import logging

from homeconnect.api import HomeConnectError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    bsh_key_to_translation_key,
    get_dict_from_home_connect_error,
    translation_key_to_bsh_key,
)
from .api import ConfigEntryAuth, HomeConnectDevice
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_SELECTED_PROGRAM,
    DOMAIN,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""

    def get_entities() -> list[HomeConnectProgramSelectEntity]:
        """Get a list of entities."""
        entities: list[HomeConnectProgramSelectEntity] = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            if device.appliance.type in APPLIANCES_WITH_PROGRAMS:
                with contextlib.suppress(HomeConnectError):
                    programs = device.appliance.get_programs_available()
                    if programs:
                        entities.extend(
                            HomeConnectProgramSelectEntity(
                                device, programs, start_on_select
                            )
                            for start_on_select in (True, False)
                        )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    def __init__(
        self, device: HomeConnectDevice, programs: list[str], start_on_select: bool
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            SelectEntityDescription(
                key=BSH_ACTIVE_PROGRAM if start_on_select else BSH_SELECTED_PROGRAM,
                translation_key="active_program"
                if start_on_select
                else "selected_program",
            ),
        )
        self._attr_options = [
            bsh_key_to_translation_key(program) for program in programs
        ]
        self.start_on_select = start_on_select

    async def async_update(self) -> None:
        """Update the program selection status."""
        program = self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE)
        self._attr_current_option = (
            bsh_key_to_translation_key(program) if program else None
        )
        _LOGGER.debug("Updated, new program: %s", self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        bsh_key = translation_key_to_bsh_key(option)
        _LOGGER.debug(
            "Tried to start program: %s"
            if self.start_on_select
            else "Tried to select program: %s",
            bsh_key,
        )
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.start_program
                if self.start_on_select
                else self.device.appliance.select_program,
                bsh_key,
            )
        except HomeConnectError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="start_program"
                if self.start_on_select
                else "select_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "program": bsh_key,
                },
            ) from err
        self.async_entity_update()
