"""Provides a switch for Home Connect."""

import contextlib
import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import HomeConnectConfigEntry, get_dict_from_home_connect_error
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    ATTR_ALLOWED_VALUES,
    ATTR_CONSTRAINTS,
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
    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .entity import HomeConnectDevice, HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


SWITCHES = (
    SwitchEntityDescription(
        key=BSH_CHILD_LOCK_STATE,
        translation_key="child_lock",
    ),
    SwitchEntityDescription(
        key="ConsumerProducts.CoffeeMaker.Setting.CupWarmer",
        translation_key="cup_warmer",
    ),
    SwitchEntityDescription(
        key=REFRIGERATION_SUPERMODEFREEZER,
        translation_key="freezer_super_mode",
    ),
    SwitchEntityDescription(
        key=REFRIGERATION_SUPERMODEREFRIGERATOR,
        translation_key="refrigerator_super_mode",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.EcoMode",
        translation_key="eco_mode",
    ),
    SwitchEntityDescription(
        key="Cooking.Oven.Setting.SabbathMode",
        translation_key="sabbath_mode",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.SabbathMode",
        translation_key="sabbath_mode",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.VacationMode",
        translation_key="vacation_mode",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.FreshMode",
        translation_key="fresh_mode",
    ),
    SwitchEntityDescription(
        key=REFRIGERATION_DISPENSER,
        translation_key="dispenser_enabled",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFridge",
        translation_key="door_assistant_fridge",
    ),
    SwitchEntityDescription(
        key="Refrigeration.Common.Setting.Door.AssistantFreezer",
        translation_key="door_assistant_freezer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities() -> list[SwitchEntity]:
        """Get a list of entities."""
        entities: list[SwitchEntity] = []
        for device in entry.runtime_data.devices:
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""

        _LOGGER.debug("Turning on %s", self.entity_description.key)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self.entity_description.key, True
            )
        except HomeConnectError as err:
            self._attr_available = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_KEY: self.bsh_key,
                },
            ) from err

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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_KEY: self.bsh_key,
                },
            ) from err

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

    def __init__(self, device: HomeConnectDevice, program_name: str) -> None:
        """Initialize the entity."""
        desc = " ".join(["Program", program_name.split(".")[-1]])
        if device.appliance.type == "WasherDryer":
            desc = " ".join(
                ["Program", program_name.split(".")[-3], program_name.split(".")[-1]]
            )
        super().__init__(device, SwitchEntityDescription(key=program_name))
        self._attr_name = f"{device.appliance.name} {desc}"
        self._attr_unique_id = f"{device.appliance.haId}-{desc}"
        self._attr_has_entity_name = False
        self.program_name = program_name

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        automations = automations_with_entity(self.hass, self.entity_id)
        scripts = scripts_with_entity(self.hass, self.entity_id)
        items = automations + scripts
        if not items:
            return

        entity_reg: er.EntityRegistry = er.async_get(self.hass)
        entity_automations = [
            automation_entity
            for automation_id in automations
            if (automation_entity := entity_reg.async_get(automation_id))
        ]
        entity_scripts = [
            script_entity
            for script_id in scripts
            if (script_entity := entity_reg.async_get(script_id))
        ]

        items_list = [
            f"- [{item.original_name}](/config/automation/edit/{item.unique_id})"
            for item in entity_automations
        ] + [
            f"- [{item.original_name}](/config/script/edit/{item.unique_id})"
            for item in entity_scripts
        ]

        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_program_switch_{self.entity_id}",
            breaks_in_ha_version="2025.6.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_program_switch",
            translation_placeholders={
                "entity_id": self.entity_id,
                "items": "\n".join(items_list),
            },
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        async_delete_issue(
            self.hass, DOMAIN, f"deprecated_program_switch_{self.entity_id}"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the program."""
        _LOGGER.debug("Tried to turn on program %s", self.program_name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.start_program, self.program_name
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "program": self.program_name,
                },
            ) from err
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the program."""
        _LOGGER.debug("Tried to stop program %s", self.program_name)
        try:
            await self.hass.async_add_executor_job(self.device.appliance.stop_program)
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                },
            ) from err
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
            SwitchEntityDescription(key=BSH_POWER_STATE, translation_key="power"),
        )
        if (
            power_state := device.appliance.status.get(BSH_POWER_STATE, {}).get(
                ATTR_VALUE
            )
        ) and power_state in [BSH_POWER_OFF, BSH_POWER_STANDBY]:
            self.power_off_state = power_state

    async def async_added_to_hass(self) -> None:
        """Add the entity to the hass instance."""
        await super().async_added_to_hass()
        if not hasattr(self, "power_off_state"):
            await self.async_fetch_power_off_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        _LOGGER.debug("Tried to switch on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, BSH_POWER_STATE, BSH_POWER_ON
            )
        except HomeConnectError as err:
            self._attr_is_on = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_on",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.device.appliance.name,
                },
            ) from err
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        if not hasattr(self, "power_off_state"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_retrieve_turn_off",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.device.appliance.name
                },
            )

        if self.power_off_state is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_not_supported",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.device.appliance.name
                },
            )
        _LOGGER.debug("tried to switch off %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                BSH_POWER_STATE,
                self.power_off_state,
            )
        except HomeConnectError as err:
            self._attr_is_on = True
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_off",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.device.appliance.name,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: self.power_off_state,
                },
            ) from err
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        if (
            self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
            == BSH_POWER_ON
        ):
            self._attr_is_on = True
        elif (
            hasattr(self, "power_off_state")
            and self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
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

    async def async_fetch_power_off_state(self) -> None:
        """Fetch the power off state."""
        try:
            data = await self.hass.async_add_executor_job(
                self.device.appliance.get, f"/settings/{self.bsh_key}"
            )
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
            return
        if not data or not (
            allowed_values := data.get(ATTR_CONSTRAINTS, {}).get(ATTR_ALLOWED_VALUES)
        ):
            return

        if BSH_POWER_OFF in allowed_values:
            self.power_off_state = BSH_POWER_OFF
        elif BSH_POWER_STANDBY in allowed_values:
            self.power_off_state = BSH_POWER_STANDBY
        else:
            self.power_off_state = None
