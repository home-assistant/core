"""Provides a switch for Home Connect."""

import logging
from typing import Any, cast

from aiohomeconnect.model import OptionKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .common import setup_home_connect_entry
from .const import BSH_POWER_OFF, BSH_POWER_ON, BSH_POWER_STANDBY, DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity, HomeConnectOptionEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

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

SWITCH_OPTIONS = (
    SwitchEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_MULTIPLE_BEVERAGES,
        translation_key="multiple_beverages",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_INTENSIV_ZONE,
        translation_key="intensiv_zone",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_BRILLIANCE_DRY,
        translation_key="brilliance_dry",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_VARIO_SPEED_PLUS,
        translation_key="vario_speed_plus",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_SILENCE_ON_DEMAND,
        translation_key="silence_on_demand",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_HALF_LOAD,
        translation_key="half_load",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_EXTRA_DRY,
        translation_key="extra_dry",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_HYGIENE_PLUS,
        translation_key="hygiene_plus",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_ECO_DRY,
        translation_key="eco_dry",
    ),
    SwitchEntityDescription(
        key=OptionKey.DISHCARE_DISHWASHER_ZEOLITE_DRY,
        translation_key="zeolite_dry",
    ),
    SwitchEntityDescription(
        key=OptionKey.COOKING_OVEN_FAST_PRE_HEAT,
        translation_key="fast_pre_heat",
    ),
    SwitchEntityDescription(
        key=OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE,
        translation_key="i_dos1_active",
    ),
    SwitchEntityDescription(
        key=OptionKey.LAUNDRY_CARE_WASHER_I_DOS_2_ACTIVE,
        translation_key="i_dos2_active",
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    entities: list[HomeConnectEntity] = []
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


def _get_option_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectOptionEntity]:
    """Get a list of currently available option entities."""
    return [
        HomeConnectSwitchOptionEntity(entry.runtime_data, appliance, description)
        for description in SWITCH_OPTIONS
        if description.key in appliance.options
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
        _get_option_entities_for_appliance,
    )


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
                    "entity_id": self.entity_id,
                    "key": self.bsh_key,
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
                    "entity_id": self.entity_id,
                    "key": self.bsh_key,
                },
            ) from err

    def update_native_value(self) -> None:
        """Update the switch's status."""
        self._attr_is_on = self.appliance.settings[SettingKey(self.bsh_key)].value


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
                    "appliance_name": self.appliance.info.name,
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
                        "appliance_name": self.appliance.info.name
                    },
                )

        if self.power_off_state is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_not_supported",
                translation_placeholders={"appliance_name": self.appliance.info.name},
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
                    "appliance_name": self.appliance.info.name,
                    "value": self.power_off_state,
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


class HomeConnectSwitchOptionEntity(HomeConnectOptionEntity, SwitchEntity):
    """Switch option class for Home Connect."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the option."""
        await self.async_set_option(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the option."""
        await self.async_set_option(False)

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        self._attr_is_on = cast(bool | None, self.option_value)
