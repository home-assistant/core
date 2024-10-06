"""Provides a switch for Home Connect."""

import contextlib
from dataclasses import dataclass
import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ConfigEntryAuth
from .const import (
    ATTR_VALUE,
    BSH_ACTIVE_PROGRAM,
    BSH_CHILD_LOCK_STATE,
    BSH_OPERATION_STATE,
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STANDBY,
    BSH_POWER_STATE,
    DOMAIN,
    REFRIGERATION_DISPENSER,
    REFRIGERATION_SUPERMODEFREEZER,
    REFRIGERATION_SUPERMODEREFRIGERATOR,
)
from .entity import HomeConnectDevice, HomeConnectEntity, HomeConnectEntityDescription

_LOGGER = logging.getLogger(__name__)

APPLIANCES_WITH_PROGRAMS = (
    "CleaningRobot",
    "CoffeeMachine",
    "Dishwasher",
    "Dryer",
    "Hood",
    "Oven",
    "WarmingDrawer",
    "Washer",
    "WasherDryer",
)


@dataclass(frozen=True, kw_only=True)
class HomeConnectSwitchEntityDescription(
    SwitchEntityDescription, HomeConnectEntityDescription
):
    """Switch entity description."""


SWITCHES = (
    HomeConnectSwitchEntityDescription(
        key=BSH_CHILD_LOCK_STATE,
        desc="Child lock",
    ),
    HomeConnectSwitchEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Setting.CupWarmer",
        desc="Cup warmer",
    ),
    HomeConnectSwitchEntityDescription(
        key=REFRIGERATION_SUPERMODEREFRIGERATOR,
        desc="Supermode refrigerator",
    ),
    HomeConnectSwitchEntityDescription(
        key=REFRIGERATION_SUPERMODEFREEZER,
        desc="Supermode freezer",
    ),
    HomeConnectSwitchEntityDescription(
        key=REFRIGERATION_SUPERMODEREFRIGERATOR,
        desc="Supermode refrigerator",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.FreshMode",
        desc="Fresh mode",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.EcoMode",
        desc="Eco mode",
    ),
    HomeConnectSwitchEntityDescription(
        key="Cooking.Oven.Setting.SabbathMode",
        desc="Sabbath mode",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.SabbathMode",
        desc="Sabbath mode",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.VacationMode",
        desc="Vacation mode",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.FreshMode",
        desc="Fresh mode",
    ),
    HomeConnectSwitchEntityDescription(
        key=REFRIGERATION_DISPENSER,
        desc="Dispenser enabled",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFridge",
        desc="Fridge door assistant fridge",
    ),
    HomeConnectSwitchEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFreezer",
        desc="Freezer door assistant freezer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities() -> list[SwitchEntity]:
        """Get a list of entities."""
        entities: list[SwitchEntity] = []
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        for device in hc_api.devices:
            if device.appliance.type in APPLIANCES_WITH_PROGRAMS:
                with contextlib.suppress(HomeConnectError):
                    programs = device.appliance.get_programs_available()
                    if programs:
                        entities.extend(
                            HomeConnectProgramSwitch(device, program)
                            for program in programs
                        )
            entities.append(HomeConnectPowerSwitch(device))
            entities.extend(
                HomeConnectSwitch(device, description)
                for description in SWITCHES
                if description.key in device.appliance.status
            )

        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSwitch(HomeConnectEntity, SwitchEntity):
    """Generic switch class for Home Connect Binary Settings."""

    entity_description: HomeConnectSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""

        _LOGGER.debug("Turning on %s", self.entity_description.key)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self.entity_description.key, True
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn on: %s", err)
            self._attr_available = False
            return

        self._attr_available = True
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off setting."""

        _LOGGER.debug("Turning off %s", self.entity_description.key)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self.entity_description.key, False
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off: %s", err)
            self._attr_available = False
            return

        self._attr_available = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""

        self._attr_is_on = self.device.appliance.status.get(
            self.entity_description.key, {}
        ).get(ATTR_VALUE)
        self._attr_available = True
        _LOGGER.debug(
            "Updated %s, new state: %s",
            self.entity_description.key,
            self._attr_is_on,
        )


class HomeConnectProgramSwitch(HomeConnectEntity, SwitchEntity):
    """Switch class for Home Connect."""

    entity_description: HomeConnectSwitchEntityDescription

    def __init__(self, device: HomeConnectDevice, program_name: str) -> None:
        """Initialize the entity."""
        desc = " ".join(["Program", program_name.split(".")[-1]])
        if device.appliance.type == "WasherDryer":
            desc = " ".join(
                ["Program", program_name.split(".")[-3], program_name.split(".")[-1]]
            )
        super().__init__(
            device, HomeConnectSwitchEntityDescription(key=program_name, desc=desc)
        )
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

    power_off_state: str | None

    def __init__(self, device: HomeConnectDevice) -> None:
        """Initialize the entity."""
        super().__init__(
            device,
            HomeConnectSwitchEntityDescription(
                key=BSH_POWER_STATE,
                desc="Power",
            ),
        )
        match device.appliance.type:
            case "Dishwasher" | "Cooktop" | "Hood":
                self.power_off_state = BSH_POWER_OFF
            case (
                "Oven"
                | "WarmDrawer"
                | "CoffeeMachine"
                | "CleaningRobot"
                | "CookProcessor"
            ):
                self.power_off_state = BSH_POWER_STANDBY
            case _:
                self.power_off_state = None

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
        if self.power_off_state is None:
            _LOGGER.debug("This appliance type does not support turning off")
            return
        _LOGGER.debug("tried to switch off %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                BSH_POWER_STATE,
                self.power_off_state,
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
            == self.power_off_state
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
