"""Provides a switch for Home Connect."""

import contextlib
import logging
from typing import Any, cast

from aiohomeconnect.model import Event, EventKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
from aiohomeconnect.model.program import EnumerateAvailableProgram

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

from .const import (
    APPLIANCES_WITH_PROGRAMS,
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

    async def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[SwitchEntity]:
        """Get a list of entities."""
        entities: list[SwitchEntity] = []
        if appliance.info.type in APPLIANCES_WITH_PROGRAMS:
            with contextlib.suppress(HomeConnectError):
                programs = (
                    await entry.runtime_data.client.get_available_programs(
                        appliance.info.ha_id
                    )
                ).programs
                if programs:
                    entities.extend(
                        HomeConnectProgramSwitch(entry.runtime_data, appliance, program)
                        for program in programs
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

        return entities

    entities = [
        entity
        for appliance in entry.runtime_data.data.values()
        for entity in await get_entities_for_appliance(appliance)
    ]
    async_add_entities(entities, True)


class HomeConnectSwitch(HomeConnectEntity, SwitchEntity):
    """Generic switch class for Home Connect Binary Settings."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on setting."""

        _LOGGER.debug("Turning on %s", self.entity_description.key)
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

        _LOGGER.debug("Turning off %s", self.entity_description.key)
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=False,
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

    async def _async_event_update_listener(self, event: Event) -> None:
        """Update status when an event for the entity is received."""
        self._attr_is_on = cast(bool, event.value)
        _LOGGER.debug(
            "Updated %s, new state: %s",
            self.entity_description.key,
            self._attr_is_on,
        )
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch's status."""
        self._attr_is_on = self.appliance.settings[SettingKey(self.bsh_key)].value
        _LOGGER.debug(
            "Updated %s, new state: %s",
            self.entity_description.key,
            self._attr_is_on,
        )


class HomeConnectProgramSwitch(HomeConnectEntity, SwitchEntity):
    """Switch class for Home Connect."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        program: EnumerateAvailableProgram,
    ) -> None:
        """Initialize the entity."""
        desc = " ".join(["Program", program.key.split(".")[-1]])
        if appliance.info.type == "WasherDryer":
            desc = " ".join(
                ["Program", program.key.split(".")[-3], program.key.split(".")[-1]]
            )
        super().__init__(
            coordinator, appliance, SwitchEntityDescription(key=program.key)
        )
        self._attr_name = f"{appliance.info.name} {desc}"
        self._attr_unique_id = f"{appliance.info.ha_id}-{desc}"
        self._attr_has_entity_name = False
        self.program = program

    async def async_added_to_hass(self) -> None:  # pylint: disable=hass-missing-super-call
        """Call when entity is added to hass."""
        self.coordinator.add_home_appliances_event_listener(
            self.appliance.info.ha_id,
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
            self._async_event_update_listener,
        )
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
        self.coordinator.delete_home_appliances_event_listener(
            self.appliance.info.ha_id,
            EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
            self._async_event_update_listener,
        )
        async_delete_issue(
            self.hass, DOMAIN, f"deprecated_program_switch_{self.entity_id}"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the program."""
        _LOGGER.debug("Tried to turn on program %s", self.program.key)
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
        _LOGGER.debug("Tried to stop program %s", self.program.key)
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

    async def _async_event_update_listener(self, event: Event) -> None:
        """Update the switch's status."""
        program = cast(str, event.value)
        self.set_native_value(program)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch's status."""

    def set_native_value(self, program: str | None) -> None:
        """Set the value of the entity."""
        if program == self.program.key:
            self._attr_is_on = True
        else:
            self._attr_is_on = False
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


class HomeConnectPowerSwitch(HomeConnectEntity, SwitchEntity):
    """Power switch class for Home Connect."""

    power_off_state: str | None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        _LOGGER.debug("Tried to switch on %s", self.name)
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
        if not hasattr(self, "power_off_state"):
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
        _LOGGER.debug("tried to switch off %s", self.name)
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

    async def _async_event_update_listener(self, event: Event) -> None:
        """Update status when an event for the entity is received."""
        self.set_native_value(cast(str, event.value))
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch's status."""
        power_state = self.appliance.settings[SettingKey.BSH_COMMON_POWER_STATE]
        self.set_native_value(cast(str, power_state.value))
        if not hasattr(self, "power_off_state"):
            await self.async_fetch_power_off_state()

    def set_native_value(self, value: str) -> None:
        """Set the value of the entity."""
        if value == BSH_POWER_ON:
            self._attr_is_on = True
        elif (
            hasattr(self, "power_off_state")
            and self.power_off_state
            and value == self.power_off_state
        ):
            self._attr_is_on = False
        elif not hasattr(self, "power_off_state") and value in [
            BSH_POWER_OFF,
            BSH_POWER_STANDBY,
        ]:
            self.power_off_state = value
            self._attr_is_on = False
        else:
            self._attr_is_on = None
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)

    async def async_fetch_power_off_state(self) -> None:
        """Fetch the power off state."""
        data = self.appliance.settings.get(
            SettingKey.BSH_COMMON_POWER_STATE,
        )
        if not data or not data.constraints or not data.constraints.allowed_values:
            try:
                data = await self.coordinator.client.get_setting(
                    self.appliance.info.ha_id,
                    setting_key=SettingKey.BSH_COMMON_POWER_STATE,
                )
            except HomeConnectError as err:
                _LOGGER.error("An error occurred: %s", err)
                return
        if not data or not data.constraints or not data.constraints.allowed_values:
            return

        if BSH_POWER_OFF in data.constraints.allowed_values:
            self.power_off_state = BSH_POWER_OFF
        elif BSH_POWER_STANDBY in data.constraints.allowed_values:
            self.power_off_state = BSH_POWER_STANDBY
        else:
            self.power_off_state = None
        return
