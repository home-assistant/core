"""Support for Insteon thermostat."""

from __future__ import annotations

from typing import Any

from pyinsteon.config import CELSIUS
from pyinsteon.constants import ThermostatMode

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities

FAN_ONLY = "fan_only"

COOLING = 1
HEATING = 2
DEHUMIDIFYING = 3
HUMIDIFYING = 4

TEMPERATURE = 10
HUMIDITY = 11
SYSTEM_MODE = 12
FAN_MODE = 13
COOL_SET_POINT = 14
HEAT_SET_POINT = 15
HUMIDITY_HIGH = 16
HUMIDITY_LOW = 17


HVAC_MODES = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.HEAT_COOL,
}
FAN_MODES = {4: FAN_AUTO, 8: FAN_ONLY}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon climate entities from a config entry."""

    @callback
    def async_add_insteon_climate_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.CLIMATE,
            InsteonClimateEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.CLIMATE}"
    async_dispatcher_connect(hass, signal, async_add_insteon_climate_entities)
    async_add_insteon_devices(
        hass,
        Platform.CLIMATE,
        InsteonClimateEntity,
        async_add_entities,
    )


class InsteonClimateEntity(InsteonEntity, ClimateEntity):
    """A Class for an Insteon climate entity."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_HUMIDITY
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = list(HVAC_MODES.values())
    _attr_fan_modes = list(FAN_MODES.values())
    _attr_min_humidity = 1
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._insteon_device.configuration[CELSIUS].value:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._insteon_device.groups[HUMIDITY].value

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODES[self._insteon_device.groups[SYSTEM_MODE].value]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._insteon_device.groups[TEMPERATURE].value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.HEAT:
            return self._insteon_device.groups[HEAT_SET_POINT].value
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.COOL:
            return self._insteon_device.groups[COOL_SET_POINT].value
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.AUTO:
            return self._insteon_device.groups[COOL_SET_POINT].value
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.AUTO:
            return self._insteon_device.groups[HEAT_SET_POINT].value
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return FAN_MODES[self._insteon_device.groups[FAN_MODE].value]

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        high = self._insteon_device.groups[HUMIDITY_HIGH].value
        low = self._insteon_device.groups[HUMIDITY_LOW].value
        # May not be loaded yet so return a default if required
        return (high + low) / 2 if high and low else None

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._insteon_device.groups[COOLING].value:
            return HVACAction.COOLING
        if self._insteon_device.groups[HEATING].value:
            return HVACAction.HEATING
        if self._insteon_device.groups[FAN_MODE].value == ThermostatMode.FAN_ALWAYS_ON:
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        """Provide attributes for display on device card."""
        attr = super().extra_state_attributes
        humidifier = "off"
        if self._insteon_device.groups[DEHUMIDIFYING].value:
            humidifier = "dehumidifying"
        if self._insteon_device.groups[HUMIDIFYING].value:
            humidifier = "humidifying"
        attr["humidifier"] = humidifier
        return attr

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.HEAT:
                await self._insteon_device.async_set_heat_set_point(target_temp)
            elif self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.COOL:
                await self._insteon_device.async_set_cool_set_point(target_temp)
        else:
            await self._insteon_device.async_set_heat_set_point(target_temp_low)
            await self._insteon_device.async_set_cool_set_point(target_temp_high)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        mode = list(FAN_MODES)[list(FAN_MODES.values()).index(fan_mode)]
        await self._insteon_device.async_set_mode(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        mode = list(HVAC_MODES)[list(HVAC_MODES.values()).index(hvac_mode)]
        await self._insteon_device.async_set_mode(mode)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new humidity level."""
        change = humidity - (self.target_humidity or 0)
        high = self._insteon_device.groups[HUMIDITY_HIGH].value + change
        low = self._insteon_device.groups[HUMIDITY_LOW].value + change
        await self._insteon_device.async_set_humidity_low_set_point(low)
        await self._insteon_device.async_set_humidity_high_set_point(high)

    async def async_added_to_hass(self) -> None:
        """Register INSTEON update events."""
        await super().async_added_to_hass()
        await self._insteon_device.async_read_op_flags()
        for group in (
            COOLING,
            HEATING,
            DEHUMIDIFYING,
            HUMIDIFYING,
            HEAT_SET_POINT,
            FAN_MODE,
            SYSTEM_MODE,
            TEMPERATURE,
            HUMIDITY,
            HUMIDITY_HIGH,
            HUMIDITY_LOW,
        ):
            self._insteon_device.groups[group].subscribe(self.async_entity_update)
