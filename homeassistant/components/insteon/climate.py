"""Support for Insteon thermostat."""
from typing import List, Optional

from pyinsteon.constants import ThermostatMode
from pyinsteon.operating_flag import CELSIUS

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

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
    0: HVAC_MODE_OFF,
    1: HVAC_MODE_HEAT,
    2: HVAC_MODE_COOL,
    3: HVAC_MODE_HEAT_COOL,
}
FAN_MODES = {4: HVAC_MODE_AUTO, 8: HVAC_MODE_FAN_ONLY}
SUPPORTED_FEATURES = (
    SUPPORT_FAN_MODE
    | SUPPORT_TARGET_HUMIDITY
    | SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_TARGET_TEMPERATURE_RANGE
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Insteon climate entities from a config entry."""

    @callback
    def async_add_insteon_climate_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            CLIMATE_DOMAIN,
            InsteonClimateEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{CLIMATE_DOMAIN}"
    async_dispatcher_connect(hass, signal, async_add_insteon_climate_entities)
    async_add_insteon_climate_entities()


class InsteonClimateEntity(InsteonEntity, ClimateEntity):
    """A Class for an Insteon climate entity."""

    @property
    def supported_features(self):
        """Return the supported features for this entity."""
        return SUPPORTED_FEATURES

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._insteon_device.properties[CELSIUS].value:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return self._insteon_device.groups[HUMIDITY].value

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODES[self._insteon_device.groups[SYSTEM_MODE].value]

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return list(HVAC_MODES.values())

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._insteon_device.groups[TEMPERATURE].value

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.HEAT:
            return self._insteon_device.groups[HEAT_SET_POINT].value
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.COOL:
            return self._insteon_device.groups[COOL_SET_POINT].value
        return None

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.AUTO:
            return self._insteon_device.groups[COOL_SET_POINT].value
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        if self._insteon_device.groups[SYSTEM_MODE].value == ThermostatMode.AUTO:
            return self._insteon_device.groups[HEAT_SET_POINT].value
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return FAN_MODES[self._insteon_device.groups[FAN_MODE].value]

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return list(FAN_MODES.values())

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        high = self._insteon_device.groups[HUMIDITY_HIGH].value
        low = self._insteon_device.groups[HUMIDITY_LOW].value
        # May not be loaded yet so return a default if required
        return (high + low) / 2 if high and low else None

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return 1

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._insteon_device.groups[COOLING].value:
            return CURRENT_HVAC_COOL
        if self._insteon_device.groups[HEATING].value:
            return CURRENT_HVAC_HEAT
        if self._insteon_device.groups[FAN_MODE].value == ThermostatMode.FAN_ALWAYS_ON:
            return CURRENT_HVAC_FAN
        return CURRENT_HVAC_IDLE

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        attr = super().device_state_attributes
        humidifier = "off"
        if self._insteon_device.groups[DEHUMIDIFYING].value:
            humidifier = "dehumidifying"
        if self._insteon_device.groups[HUMIDIFYING].value:
            humidifier = "humidifying"
        attr["humidifier"] = humidifier
        return attr

    async def async_set_temperature(self, **kwargs) -> None:
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

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        mode = list(HVAC_MODES)[list(HVAC_MODES.values()).index(hvac_mode)]
        await self._insteon_device.async_set_mode(mode)

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        change = humidity - self.target_humidity
        high = self._insteon_device.groups[HUMIDITY_HIGH].value + change
        low = self._insteon_device.groups[HUMIDITY_LOW].value + change
        await self._insteon_device.async_set_humidity_low_set_point(low)
        await self._insteon_device.async_set_humidity_high_set_point(high)

    async def async_added_to_hass(self):
        """Register INSTEON update events."""
        await super().async_added_to_hass()
        await self._insteon_device.async_read_op_flags()
        for group in [
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
        ]:
            self._insteon_device.groups[group].subscribe(self.async_entity_update)
