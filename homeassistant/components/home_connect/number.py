"""Provides number enties for Home Connect."""

import logging
from typing import cast

from aiohomeconnect.model import GetSetting, SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SVE_TRANSLATION_KEY_SET_SETTING,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .coordinator import HomeConnectConfigEntry
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)


NUMBERS = (
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_FRIDGE_FREEZER_SETPOINT_TEMPERATURE_REFRIGERATOR,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="refrigerator_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_FRIDGE_FREEZER_SETPOINT_TEMPERATURE_FREEZER,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="freezer_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_BOTTLE_COOLER_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="bottle_cooler_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_CHILLER_LEFT_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="chiller_left_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_CHILLER_COMMON_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="chiller_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_CHILLER_RIGHT_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="chiller_right_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_WINE_COMPARTMENT_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="wine_compartment_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_WINE_COMPARTMENT_2_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="wine_compartment_2_setpoint_temperature",
    ),
    NumberEntityDescription(
        key=SettingKey.REFRIGERATION_COMMON_WINE_COMPARTMENT_3_SETPOINT_TEMPERATURE,
        device_class=NumberDeviceClass.TEMPERATURE,
        translation_key="wine_compartment_3_setpoint_temperature",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect number."""
    async_add_entities(
        [
            HomeConnectNumberEntity(entry.runtime_data, appliance, description)
            for description in NUMBERS
            for appliance in entry.runtime_data.data.values()
            if description.key in appliance.settings
        ],
    )


class HomeConnectNumberEntity(HomeConnectEntity, NumberEntity):
    """Number setting class for Home Connect."""

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        _LOGGER.debug(
            "Tried to set value %s to %s for %s",
            value,
            self.bsh_key,
            self.entity_id,
        )
        try:
            await self.coordinator.client.set_setting(
                self.appliance.info.ha_id,
                setting_key=SettingKey(self.bsh_key),
                value=value,
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=SVE_TRANSLATION_KEY_SET_SETTING,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: self.entity_id,
                    SVE_TRANSLATION_PLACEHOLDER_KEY: self.bsh_key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: str(value),
                },
            ) from err

    async def async_fetch_constraints(self) -> None:
        """Fetch the max and min values and step for the number entity."""
        try:
            data = await self.coordinator.client.get_setting(
                self.appliance.info.ha_id, setting_key=SettingKey(self.bsh_key)
            )
        except HomeConnectError as err:
            _LOGGER.error("An error occurred: %s", err)
        else:
            self.set_constraints(data)

    def set_constraints(self, setting: GetSetting) -> None:
        """Set constraints for the number entity."""
        if not (constraints := setting.constraints):
            return
        if constraints.max:
            self._attr_native_max_value = constraints.max
        if constraints.min:
            self._attr_native_min_value = constraints.min
        if constraints.step_size:
            self._attr_native_step = constraints.step_size
        else:
            self._attr_native_step = 0.1 if setting.type == "Double" else 1

    def update_native_value(self) -> None:
        """Update status when an event for the entity is received."""
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_native_value = cast(float, data.value)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        data = self.appliance.settings[cast(SettingKey, self.bsh_key)]
        self._attr_native_unit_of_measurement = data.unit
        self.set_constraints(data)
        if (
            not hasattr(self, "_attr_native_min_value")
            or not hasattr(self, "_attr_native_max_value")
            or not hasattr(self, "_attr_native_step")
        ):
            await self.async_fetch_constraints()
