"""Provides a switch for Home Connect."""

import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_OPERATION_STATE,
    BSH_POWER_ON,
    BSH_POWER_STATE,
    DOMAIN,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("switch", [])
            _LOGGER.debug("Switch Entities: %s", entity_dicts)
            entity_list = [
                (
                    HomeConnectProgramSwitch(**d)
                    if d.get("program_name")
                    else HomeConnectSwitch(**d)
                )
                for d in entity_dicts
            ]
            entity_list += [HomeConnectPowerSwitch(device_dict[CONF_DEVICE])]
            entities += entity_list
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSwitch(HomeConnectEntity, SwitchEntity):
    """Generic switch class for Home Connect Binary Settings."""

    def __init__(self, device, key, desc):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._key = key
        self._attr_available = False

    def turn_on(self, **kwargs: Any) -> None:
        """Tuen on setting."""

        _LOGGER.debug("Turning on %s", self._key)
        try:
            self.device.appliance.set_setting(self._key, True)
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn on: %s", err)
            return

        self._attr_available = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off setting."""

        _LOGGER.debug("Turning off %s", self._key)
        try:
            self.device.appliance.set_setting(self._key, False)
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off: %s", err)
            self._attr_available = False
            return

        self._attr_available = True

    def update(self) -> None:
        """Update the switch's status."""

        state = self.device.appliance.status.get(self._key, {})
        self._attr_is_on = state.get(ATTR_VALUE)
        self._attr_available = True
        _LOGGER.debug("Updated %s, new state: %s", self._key, self._attr_is_on)


class HomeConnectProgramSwitch(HomeConnectEntity, SwitchEntity):
    """Switch class for Home Connect."""

    def __init__(self, device, program_name):
        """Initialize the entity."""
        desc = " ".join(["Program", program_name.split(".")[-1]])
        if device.appliance.type == "WasherDryer":
            desc = " ".join(
                ["Program", program_name.split(".")[-3], program_name.split(".")[-1]]
            )
        super().__init__(device, desc)
        self.program_name = program_name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the program."""
        _LOGGER.debug("Tried to turn on program %s", self.program_name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.start_program, self.program_name
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to start program: %s", err)
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the program."""
        _LOGGER.debug("Tried to stop program %s", self.program_name)
        try:
            await self.hass.async_add_executor_job(self.device.appliance.stop_program)
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to stop program: %s", err)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        state = self.device.appliance.status.get(BSH_ACTIVE_PROGRAM, {})
        if state.get(ATTR_VALUE) == self.program_name:
            self._attr_is_on = True
        else:
            self._attr_is_on = False
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


class HomeConnectPowerSwitch(HomeConnectEntity, SwitchEntity):
    """Power switch class for Home Connect."""

    def __init__(self, device):
        """Inititialize the entity."""
        super().__init__(device, "Power")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        _LOGGER.debug("Tried to switch on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, BSH_POWER_STATE, BSH_POWER_ON
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn on device: %s", err)
            self._attr_is_on = False
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        _LOGGER.debug("tried to switch off %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                BSH_POWER_STATE,
                self.device.power_off_state,
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off device: %s", err)
            self._attr_is_on = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        if (
            self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
            == BSH_POWER_ON
        ):
            self._attr_is_on = True
        elif (
            self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
            == self.device.power_off_state
        ):
            self._attr_is_on = False
        elif self.device.appliance.status.get(BSH_OPERATION_STATE, {}).get(
            ATTR_VALUE, None
        ) in [
            "BSH.Common.EnumType.OperationState.Ready",
            "BSH.Common.EnumType.OperationState.DelayedStart",
            "BSH.Common.EnumType.OperationState.Run",
            "BSH.Common.EnumType.OperationState.Pause",
            "BSH.Common.EnumType.OperationState.ActionRequired",
            "BSH.Common.EnumType.OperationState.Aborting",
            "BSH.Common.EnumType.OperationState.Finished",
        ]:
            self._attr_is_on = True
        elif (
            self.device.appliance.status.get(BSH_OPERATION_STATE, {}).get(ATTR_VALUE)
            == "BSH.Common.EnumType.OperationState.Inactive"
        ):
            self._attr_is_on = False
        else:
            self._attr_is_on = None
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)
