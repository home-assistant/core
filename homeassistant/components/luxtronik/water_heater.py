"""Luxtronik water heater component."""
# region Imports
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import HVACAction
from homeassistant.components.water_heater import (
    ENTITY_ID_FORMAT,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import LuxtronikEntity
from .common import get_sensor_data
from .const import (
    CONF_COORDINATOR,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    DeviceKey,
    LuxCalculation,
    LuxMode,
    LuxOperationMode,
    LuxParameter,
    LuxVisibility,
)
from .coordinator import LuxtronikCoordinator, LuxtronikCoordinatorData
from .model import LuxtronikWaterHeaterDescription

# endregion Imports

# region Const
OPERATION_MAPPING: dict[str, str] = {
    LuxMode.off.value: STATE_OFF,
    LuxMode.automatic.value: STATE_HEAT_PUMP,
    LuxMode.second_heatsource.value: STATE_ELECTRIC,
    LuxMode.party.value: STATE_PERFORMANCE,
    LuxMode.holidays.value: STATE_HEAT_PUMP,
}

WATER_HEATERS: list[LuxtronikWaterHeaterDescription] = [
    LuxtronikWaterHeaterDescription(
        key="domestic_water",
        operation_list=[STATE_OFF, STATE_HEAT_PUMP, STATE_ELECTRIC, STATE_PERFORMANCE],
        supported_features=WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.AWAY_MODE,
        luxtronik_key=LuxParameter.P0004_MODE_DOMESTIC_WATER,
        luxtronik_key_current_temperature=LuxCalculation.C0017_DOMESTIC_WATER_TEMPERATURE,
        luxtronik_key_target_temperature=LuxParameter.P0002_DOMESTIC_WATER_TARGET_TEMPERATURE,
        luxtronik_key_current_action=LuxCalculation.C0080_STATUS,
        luxtronik_action_heating=LuxOperationMode.domestic_water,
        # luxtronik_key_target_temperature_high=LuxParameter,
        # luxtronik_key_target_temperature_low=LuxParameter,
        icon="mdi:water-boiler",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        visibility=LuxVisibility.V0029_DOMESTIC_WATER_TEMPERATURE,
    )
]
# endregion Const


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize DHW device from config entry."""
    data: dict = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: LuxtronikCoordinator = data[CONF_COORDINATOR]
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        LuxtronikWaterHeater(hass, config_entry, coordinator, description)
        for description in WATER_HEATERS
        if coordinator.entity_active(description)
    )


class LuxtronikWaterHeater(LuxtronikEntity, WaterHeaterEntity):
    """Representation of an Luxtronik water heater."""

    entity_description: LuxtronikWaterHeaterDescription

    _attr_min_temp = 40.0
    _attr_max_temp = 65.0
    _attr_target_temperature_low = 45.0
    _attr_target_temperature_high = 65.0

    _last_operation_mode_before_away: str | None = None
    _current_action: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikWaterHeaterDescription,
    ) -> None:
        """Init Luxtronik Switch."""
        super().__init__(
            coordinator=coordinator,
            description=description,
            device_info_ident=DeviceKey.domestic_water,
            platform=Platform.WATER_HEATER,
        )
        prefix = entry.data[CONF_HA_SENSOR_PREFIX]
        self.entity_id = ENTITY_ID_FORMAT.format(f"{prefix}_{description.key}")
        self._attr_unique_id = self.entity_id
        self._attr_temperature_unit = str(description.unit_of_measurement)
        self._attr_operation_list = description.operation_list
        self._attr_supported_features = description.supported_features

        self._sensor_data = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return the current running hvac operation."""
        if (
            self.entity_description.luxtronik_action_heating is not None
            and self._current_action
            == self.entity_description.luxtronik_action_heating.value
        ):
            return HVACAction.HEATING
        return HVACAction.OFF

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        result_icon = str(self.entity_description.icon)
        if self._attr_current_operation == STATE_OFF:
            result_icon += "-off"
        elif self._attr_current_operation == STATE_HEAT_PUMP:
            result_icon += "-auto"
        return result_icon

    async def _data_update(self, event):
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(
        self, data: LuxtronikCoordinatorData | None = None
    ) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data if data is None else data
        if data is None:
            return
        mode = get_sensor_data(data, self.entity_description.luxtronik_key.value)
        self._attr_current_operation = None if mode is None else OPERATION_MAPPING[mode]
        self._current_action = get_sensor_data(
            data, self.entity_description.luxtronik_key_current_action.value
        )
        self._attr_is_away_mode_on = (
            None if mode is None else mode == LuxMode.holidays.value
        )
        if not self._attr_is_away_mode_on:
            self._last_operation_mode_before_away = None
        self._attr_current_temperature = get_sensor_data(
            data, self.entity_description.luxtronik_key_current_temperature.value
        )
        self._attr_target_temperature = get_sensor_data(
            data, self.entity_description.luxtronik_key_target_temperature.value
        )
        super()._handle_coordinator_update()

    async def _async_set_lux_mode(self, lux_mode: str) -> None:
        lux_key = self.entity_description.luxtronik_key.value
        data = await self.coordinator.async_write(lux_key.split(".")[1], lux_mode)
        self._handle_coordinator_update(data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        value = kwargs.get(ATTR_TEMPERATURE)
        lux_key = self.entity_description.luxtronik_key_target_temperature.value
        data: LuxtronikCoordinatorData | None = await self.coordinator.async_write(
            lux_key.split(".")[1], value
        )
        self._handle_coordinator_update(data)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        lux_mode = [k for k, v in OPERATION_MAPPING.items() if v == operation_mode][0]
        await self._async_set_lux_mode(lux_mode)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self._last_operation_mode_before_away = self._attr_current_operation
        await self._async_set_lux_mode(LuxMode.holidays.value)

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        if self._last_operation_mode_before_away is None or (
            self._attr_operation_list is not None
            and self._last_operation_mode_before_away not in self._attr_operation_list
        ):
            await self._async_set_lux_mode(LuxMode.automatic.value)
        else:
            await self.async_set_operation_mode(self._last_operation_mode_before_away)
