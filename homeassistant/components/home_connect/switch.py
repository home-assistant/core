"""Provides a switch for Home Connect."""

import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import (
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
    ATTR_VALUE,
    BSH_OPERATION_STATE,
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STANDBY,
    BSH_POWER_STATE,
    DOMAIN,
)
from .entity import HomeConnectEntityDescription, HomeConnectInteractiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        return [
            switch_entity
            for device in hc_api.devices
            for switch_entity in (
                HomeConnectPowerSwitch(
                    device, HomeConnectPowerSwitch.get_switch_off_state(device)
                ),
                *[
                    HomeConnectSwitchEntity(device, setting)
                    for setting in BSH_BINARY_SETTINGS
                    if setting.key in device.appliance.status
                ],
            )
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSwitchEntityDescription(
    HomeConnectEntityDescription, SwitchEntityDescription
):
    """Description of a Home Connect switch entity."""


class HomeConnectSwitchEntity(HomeConnectInteractiveEntity, SwitchEntity):
    """Setting switch class for Home Connect."""

    entity_description: HomeConnectSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch setting on."""
        if not await self.async_set_value_to_appliance(True):
            self._attr_is_on = False
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch setting off."""
        if not await self.async_set_value_to_appliance(False):
            self._attr_is_on = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        self._attr_is_on = False
        if self.status.get(ATTR_VALUE):
            self._attr_is_on = True
        _LOGGER.debug("Updated %s, new state: %s", self.bsh_key, self._attr_is_on)


class HomeConnectPowerSwitch(HomeConnectSwitchEntity):
    """Power switch class for Home Connect."""

    power_off_state: str | None = None

    def __init__(self, device: HomeConnectDevice, power_off_state: str | None) -> None:
        """Initialize the entity."""
        super().__init__(
            device, HomeConnectSwitchEntityDescription(key=BSH_POWER_STATE)
        )
        self.power_off_state = power_off_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        if not await self.async_set_value_to_appliance(BSH_POWER_ON):
            self._attr_is_on = False
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        if self.power_off_state is None:
            _LOGGER.error(
                "Power off state is not defined for device %s, cannot turn off",
                self.name,
            )
        if not await self.async_set_value_to_appliance(self.power_off_state):
            self._attr_is_on = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        if self.status.get(ATTR_VALUE) == BSH_POWER_ON:
            self._attr_is_on = True
        elif self.status.get(ATTR_VALUE) == self.power_off_state:
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

        if self.power_off_state is not None:
            return

        await self.hass.async_add_executor_job(self.get_switch_off_state, self.device)

    @staticmethod
    def get_switch_off_state(device: HomeConnectDevice) -> str | None:
        """Get the power off state of the device."""
        try:
            data = device.appliance.get(f"/settings/{BSH_POWER_STATE}")
        except HomeConnectError as err:
            _LOGGER.error("An error occurred while getting switch off state: %s", err)
            return None
        if (
            not data
            or not (constraints := data.get(ATTR_CONSTRAINTS))
            or not (allowed_values := constraints.get(ATTR_ALLOWED_VALUES))
        ):
            return None
        return (
            BSH_POWER_STANDBY if BSH_POWER_STANDBY in allowed_values else BSH_POWER_OFF
        )


BSH_BINARY_SETTINGS = (
    HomeConnectEntityDescription(key="BSH.Common.Setting.ChildLock"),
    HomeConnectEntityDescription(key="ConsumerProducts.CoffeeMaker.Setting.CupWarmer"),
    HomeConnectEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SuperModeRefrigerator"
    ),
    HomeConnectEntityDescription(
        key="Refrigeration.FridgeFreezer.Setting.SuperModeFreezer"
    ),
    HomeConnectEntityDescription(key="Refrigeration.Common.Setting.EcoMode"),
    HomeConnectEntityDescription(key="Cooking.Oven.Setting.SabbathMode"),
    HomeConnectEntityDescription(key="Refrigeration.Common.Setting.SabbathMode"),
    HomeConnectEntityDescription(key="Refrigeration.Common.Setting.VacationMode"),
    HomeConnectEntityDescription(key="Refrigeration.Common.Setting.FreshMode"),
    HomeConnectEntityDescription(key="Refrigeration.Common.Setting.Dispenser.Enabled"),
    HomeConnectEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFridge"
    ),
    HomeConnectEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFreezer"
    ),
)
