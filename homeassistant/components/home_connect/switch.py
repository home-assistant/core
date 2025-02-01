"""Provides a switch for Home Connect."""

import logging
from typing import Any, cast

from aiohomeconnect.model import EventKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import EnumerateProgram

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
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import (
    BSH_POWER_OFF,
    BSH_POWER_ON,
    BSH_POWER_STANDBY,
    DOMAIN,
    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)


SWITCHES = (
    SwitchEntityDescription(
        key=SettingKey.BSH_COMMON_CHILD_LOCK,
        translation_key="child_lock",
    ),
    SwitchEntityDescription(
        key=SettingKey.CONSUMER_PRODUCTS_COFFEE_MAKER_CUP_WARMER,
        translation_key="cup_warmer",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER,
        translation_key="freezer_super_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_REFRIGERATOR,
        translation_key="refrigerator_super_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_ECO_MODE,
        translation_key="eco_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.COOKING_OVEN_SABBATH_MODE,
        translation_key="sabbath_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_SABBATH_MODE,
        translation_key="sabbath_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_VACATION_MODE,
        translation_key="vacation_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_FRESH_MODE,
        translation_key="fresh_mode",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_DISPENSER_ENABLED,
        translation_key="dispenser_enabled",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_DOOR_ASSISTANT_FRIDGE,
        translation_key="door_assistant_fridge",
    ),
    SwitchEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_DOOR_ASSISTANT_FREEZER,
        translation_key="door_assistant_freezer",
    ),
)


POWER_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key=SettingKey.BSH_COMMON_POWER_STATE,
    translation_key="power",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    entities: list[SwitchEntity] = []
    for appliance in entry.runtime_data.data.values():
        entities.extend(
            HomeConnectProgramSwitch(entry.runtime_data, appliance, program)
            for program in appliance.programs
            if program.key != ProgramKey.UNKNOWN
        )
        if SettingKey.BSH_COMMON_POWER_STATE in appliance.settings:
            entities.append(
                HomeConnectPowerSwitch(
                    entry.runtime_data, appliance, POWER_SWITCH_DESCRIPTION
                )
            )
        entities.extend(
            HomeConnectSwitch(entry.runtime_data, appliance, description)
            for description in SWITCHES
            if description.key in appliance.settings
        )

    async_add_entities(entities)


class HomeConnectSwitch(HomeConnectEntity, SwitchEntity):
    """Generic switch class for Home Connect Binary Settings."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=True,
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

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off setting."""
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=False,
            )
        except HomeConnectError as err:
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

    def update_native_value(self) -> None:
        """Update the switch's status."""
        self._attr_is_on = self.appliance.settings[SettingKey(self.bsh_key)].value


class HomeConnectProgramSwitch(HomeConnectEntity, SwitchEntity):
    """Switch class for Home Connect."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        program: EnumerateProgram,
    ) -> None:
        """Initialize the entity."""
        desc = " ".join(["Program", program.key.split(".")[-1]])
        if appliance.info.type == "WasherDryer":
            desc = " ".join(
                ["Program", program.key.split(".")[-3], program.key.split(".")[-1]]
            )
        super().__init__(
            coordinator,
            appliance,
            SwitchEntityDescription(key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM),
        )
        self._attr_name = f"{appliance.info.name} {desc}"
        self._attr_unique_id = f"{appliance.info.ha_id}-{desc}"
        self._attr_has_entity_name = False
        self.program = program

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
        try:
            await self.coordinator.client.start_program(
                self.appliance.info.ha_id, program_key=self.program.key
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "program": self.program.key,
                },
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the program."""
        try:
            await self.coordinator.client.stop_program(self.appliance.info.ha_id)
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                },
            ) from err

    def update_native_value(self) -> None:
        """Update the switch's status based on if the program related to this entity is currently active."""
        event = self.appliance.events.get(EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM)
        self._attr_is_on = bool(event and event.value == self.program.key)


class HomeConnectPowerSwitch(HomeConnectEntity, SwitchEntity):
    """Power switch class for Home Connect."""

    power_off_state: str | None | UndefinedType = UNDEFINED

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                value=BSH_POWER_ON,
            )
        except HomeConnectError as err:
            self._attr_is_on = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_on",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.appliance.info.name,
                },
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        if self.power_off_state is UNDEFINED:
            await self.async_fetch_power_off_state()
            if self.power_off_state is UNDEFINED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_retrieve_turn_off",
                    translation_placeholders={
                        SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.appliance.info.name
                    },
                )

        if self.power_off_state is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_not_supported",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.appliance.info.name
                },
            )
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                value=self.power_off_state,
            )
        except HomeConnectError as err:
            self._attr_is_on = True
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_off",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME: self.appliance.info.name,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: self.power_off_state,
                },
            ) from err

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        power_state = self.appliance.settings[SettingKey.BSH_COMMON_POWER_STATE]
        value = cast(str, power_state.value)
        if value == BSH_POWER_ON:
            self._attr_is_on = True
        elif (
            isinstance(self.power_off_state, str)
            and self.power_off_state
            and value == self.power_off_state
        ):
            self._attr_is_on = False
        elif self.power_off_state is UNDEFINED and value in [
            BSH_POWER_OFF,
            BSH_POWER_STANDBY,
        ]:
            self.power_off_state = value
            self._attr_is_on = False
        else:
            self._attr_is_on = None

    async def async_fetch_power_off_state(self) -> None:
        """Fetch the power off state."""
        data = self.appliance.settings[SettingKey.BSH_COMMON_POWER_STATE]

        if not data.constraints or not data.constraints.allowed_values:
            try:
                data = await self.coordinator.client.get_setting(
                    self.appliance.info.ha_id,
                    setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                )
            except HomeConnectError as err:
                _LOGGER.error("An error occurred fetching the power settings: %s", err)
                return
        if not data.constraints or not data.constraints.allowed_values:
            return

        if BSH_POWER_OFF in data.constraints.allowed_values:
            self.power_off_state = BSH_POWER_OFF
        elif BSH_POWER_STANDBY in data.constraints.allowed_values:
            self.power_off_state = BSH_POWER_STANDBY
        else:
            self.power_off_state = None
