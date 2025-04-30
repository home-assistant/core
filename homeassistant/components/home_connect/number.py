"""Provides number entities for Home Connect."""

import logging
from typing import cast

from aiohomeconnect.model import GetSetting, OptionKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import DOMAIN, UNIT_MAP
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity, HomeConnectOptionEntity, constraint_fetcher
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

NUMBERS = (
    NumberEntityDescription(
        key=SettingKey.BSH_COMMON_ALARM_CLOCK,
        device_class=NumberDeviceClass.DURATION,
        translation_key="alarm_clock",
    ),
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
    NumberEntityDescription(
        key=SettingKey.COOKING_HOOD_COLOR_TEMPERATURE_PERCENT,
        translation_key="color_temperature_percent",
        native_unit_of_measurement="%",
    ),
    NumberEntityDescription(
        key=SettingKey.LAUNDRY_CARE_WASHER_I_DOS_1_BASE_LEVEL,
        device_class=NumberDeviceClass.VOLUME,
        translation_key="washer_i_dos_1_base_level",
    ),
    NumberEntityDescription(
        key=SettingKey.LAUNDRY_CARE_WASHER_I_DOS_2_BASE_LEVEL,
        device_class=NumberDeviceClass.VOLUME,
        translation_key="washer_i_dos_2_base_level",
    ),
)

NUMBER_OPTIONS = (
    NumberEntityDescription(
        key=OptionKey.BSH_COMMON_DURATION,
        translation_key="duration",
    ),
    NumberEntityDescription(
        key=OptionKey.BSH_COMMON_FINISH_IN_RELATIVE,
        translation_key="finish_in_relative",
    ),
    NumberEntityDescription(
        key=OptionKey.BSH_COMMON_START_IN_RELATIVE,
        translation_key="start_in_relative",
    ),
    NumberEntityDescription(
        key=OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_FILL_QUANTITY,
        translation_key="fill_quantity",
        device_class=NumberDeviceClass.VOLUME,
        native_step=1,
    ),
    NumberEntityDescription(
        key=OptionKey.COOKING_OVEN_SETPOINT_TEMPERATURE,
        translation_key="setpoint_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        HomeConnectNumberEntity(entry.runtime_data, appliance, description)
        for description in NUMBERS
        if description.key in appliance.settings
    ]


def _get_option_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectOptionEntity]:
    """Get a list of currently available option entities."""
    return [
        HomeConnectOptionNumberEntity(entry.runtime_data, appliance, description)
        for description in NUMBER_OPTIONS
        if description.key in appliance.options
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect number."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
        _get_option_entities_for_appliance,
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
                translation_key="set_setting_entity",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "entity_id": self.entity_id,
                    "key": self.bsh_key,
                    "value": str(value),
                },
            ) from err

    @constraint_fetcher
    async def async_fetch_constraints(self) -> None:
        """Fetch the max and min values and step for the number entity."""
        setting_key = cast(SettingKey, self.bsh_key)
        data = self.appliance.settings.get(setting_key)
        if not data or not data.unit or not data.constraints:
            data = await self.coordinator.client.get_setting(
                self.appliance.info.ha_id, setting_key=setting_key
            )
            if data.unit:
                self._attr_native_unit_of_measurement = data.unit
            self.set_constraints(data)

    def set_constraints(self, setting: GetSetting) -> None:
        """Set constraints for the number entity."""
        if setting.unit:
            self._attr_native_unit_of_measurement = UNIT_MAP.get(
                setting.unit, setting.unit
            )
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
        self.set_constraints(data)
        if (
            not hasattr(self, "_attr_native_unit_of_measurement")
            or not hasattr(self, "_attr_native_min_value")
            or not hasattr(self, "_attr_native_max_value")
            or not hasattr(self, "_attr_native_step")
        ):
            await self.async_fetch_constraints()


class HomeConnectOptionNumberEntity(HomeConnectOptionEntity, NumberEntity):
    """Number option class for Home Connect."""

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        await self.async_set_option(value)

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        self._attr_native_value = cast(float | None, self.option_value)
        option_definition = self.appliance.options.get(self.bsh_key)
        if option_definition:
            if option_definition.unit:
                candidate_unit = UNIT_MAP.get(
                    option_definition.unit, option_definition.unit
                )
                if (
                    not hasattr(self, "_attr_native_unit_of_measurement")
                    or candidate_unit != self._attr_native_unit_of_measurement
                ):
                    self._attr_native_unit_of_measurement = candidate_unit
            option_constraints = option_definition.constraints
            if option_constraints:
                if (
                    not hasattr(self, "_attr_native_min_value")
                    or self._attr_native_min_value != option_constraints.min
                ) and option_constraints.min:
                    self._attr_native_min_value = option_constraints.min
                if (
                    not hasattr(self, "_attr_native_max_value")
                    or self._attr_native_max_value != option_constraints.max
                ) and option_constraints.max:
                    self._attr_native_max_value = option_constraints.max
                if (
                    not hasattr(self, "_attr_native_step")
                    or self._attr_native_step != option_constraints.step_size
                ) and option_constraints.step_size:
                    self._attr_native_step = option_constraints.step_size
