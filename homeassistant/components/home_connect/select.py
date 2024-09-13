"""Provides a selector for Home Connect."""

import contextlib
import logging
from typing import cast

from homeconnect.api import HomeConnectError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import (
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    DOMAIN,
)
from .entity import HomeConnectEntityDescription, HomeConnectInteractiveEntity
from .utils import bsh_key_to_translation_key, translation_key_to_bsh_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        entities: list[HomeConnectSelectEntity] = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            entities += [
                HomeConnectSelectEntity(device, desc)
                for desc in BSH_SELECT_SETTINGS
                if desc.key in device.appliance.status
            ]
            with contextlib.suppress(HomeConnectError):
                if device.appliance.get_programs_available():
                    entities.append(HomeConnectProgramSelectEntity(device))
        for entity in entities:
            with contextlib.suppress(HomeConnectError):
                entity.get_options()
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSelectEntityDescription(
    HomeConnectEntityDescription,
    SelectEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect select entity."""


class HomeConnectSelectEntity(HomeConnectInteractiveEntity, SelectEntity):
    "Select class for Home Connect."

    entity_description: HomeConnectSelectEntityDescription

    def get_options(self):
        """Get the options for this sensor."""
        try:
            data = self.device.appliance.get(f"/status/{self.bsh_key}")
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
            self._attr_options = []
            return
        if (
            not data
            or not (constraints := data.get(ATTR_CONSTRAINTS))
            or not (options := constraints.get(ATTR_ALLOWED_VALUES))
        ):
            self._attr_options = []
            return
        self._attr_options = [bsh_key_to_translation_key(option) for option in options]

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        bsh_option_key = translation_key_to_bsh_key(option)
        await self.async_set_value_to_appliance(bsh_option_key)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the select entity current option and options."""
        original_value = self.status.get(ATTR_VALUE)
        self._attr_current_option = (
            bsh_key_to_translation_key(cast(str, original_value))
            if original_value
            else None
        )
        if not self.options:
            await self.hass.async_add_executor_job(self.get_options)
        _LOGGER.debug("Updated, new state: %s", original_value)


class HomeConnectProgramSelectEntity(HomeConnectSelectEntity):
    """Program select entity for Home Connect."""

    def __init__(self, device: HomeConnectDevice) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            HomeConnectSelectEntityDescription(
                key="program",
            ),
        )

    def get_options(self):
        """Get the options for this sensor."""
        self._attr_options = [
            bsh_key_to_translation_key(program)
            for program in self.device.appliance.get_programs_available()
        ]

    async def async_update(self) -> None:
        """Update the program selection status."""
        original_value = self.device.appliance.status.get(BSH_ACTIVE_PROGRAM, {}).get(
            ATTR_VALUE
        )
        self._attr_current_option = bsh_key_to_translation_key(original_value)
        _LOGGER.debug("Updated, new program: %s", original_value)

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        bsh_key = translation_key_to_bsh_key(option)
        _LOGGER.debug("Tried to select program: %s", bsh_key)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.start_program, bsh_key
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to select program %s: %s", bsh_key, err)
        self.async_entity_update()


BSH_SELECT_SETTINGS = (
    HomeConnectSelectEntityDescription(
        key="ConsumerProducts.CleaningRobot.Setting.CurrentMap",
    ),
)
