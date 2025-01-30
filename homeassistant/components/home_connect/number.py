"""Provides number enties for Home Connect."""

from collections.abc import Callable
import logging
from typing import cast

from aiohomeconnect.model import EventKey, GetSetting, SettingKey
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
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
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

    def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[HomeConnectNumberEntity]:
        """Get a list of entities."""
        remove_listener: Callable[[], None] | None = None

        def handle_removed_device() -> None:
            """Handle removed device."""
            for entity_unique_id in added_entities.copy():
                if entity_unique_id and appliance.info.ha_id in entity_unique_id:
                    added_entities.remove(entity_unique_id)
            assert remove_listener
            remove_listener()

        remove_listener = entry.runtime_data.async_add_listener(
            handle_removed_device,
            (appliance.info.ha_id, EventKey.BSH_COMMON_APPLIANCE_DEPAIRED),
        )
        entry.async_on_unload(remove_listener)

        return [
            HomeConnectNumberEntity(entry.runtime_data, appliance, description)
            for description in NUMBERS
            if description.key in appliance.settings
        ]

    entities = [
        entity
        for appliance in entry.runtime_data.data.values()
        for entity in get_entities_for_appliance(appliance)
    ]
    async_add_entities(entities)

    added_entities = {entity.unique_id for entity in entities}

    def handle_paired_or_connected_device() -> None:
        """Handle new paired device or a device that has been connected."""
        for appliance in entry.runtime_data.data.values():
            new_entities = [
                entity
                for entity in get_entities_for_appliance(appliance)
                if entity.unique_id not in added_entities
            ]
            async_add_entities(new_entities)
            added_entities.update(entity.unique_id for entity in new_entities)

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(handle_paired_or_connected_device)
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
