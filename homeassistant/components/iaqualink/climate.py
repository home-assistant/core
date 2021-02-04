"""Support for Aqualink Thermostats."""
import logging
from typing import List, Optional

from iaqualink import AqualinkHeater, AqualinkPump, AqualinkSensor, AqualinkState
from iaqualink.const import (
    AQUALINK_TEMP_CELSIUS_HIGH,
    AQUALINK_TEMP_CELSIUS_LOW,
    AQUALINK_TEMP_FAHRENHEIT_HIGH,
    AQUALINK_TEMP_FAHRENHEIT_LOW,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    DOMAIN,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import HomeAssistantType

from . import AqualinkEntity, refresh_system
from .const import CLIMATE_SUPPORTED_MODES, DOMAIN as AQUALINK_DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkThermostat(dev))
    async_add_entities(devs, True)


class HassAqualinkThermostat(AqualinkEntity, ClimateEntity):
    """Representation of a thermostat."""

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self.dev.label.split(" ")[0]

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of supported HVAC modes."""
        return CLIMATE_SUPPORTED_MODES

    @property
    def pump(self) -> AqualinkPump:
        """Return the pump device for the current thermostat."""
        pump = f"{self.name.lower()}_pump"
        return self.dev.system.devices[pump]

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode."""
        state = AqualinkState(self.heater.state)
        if state == AqualinkState.ON:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @refresh_system
    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Turn the underlying heater switch on or off."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self.heater.turn_on()
        elif hvac_mode == HVAC_MODE_OFF:
            await self.heater.turn_off()
        else:
            _LOGGER.warning("Unknown operation mode: %s", hvac_mode)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.dev.system.temp_unit == "F":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature supported by the thermostat."""
        if self.temperature_unit == TEMP_FAHRENHEIT:
            return AQUALINK_TEMP_FAHRENHEIT_LOW
        return AQUALINK_TEMP_CELSIUS_LOW

    @property
    def max_temp(self) -> int:
        """Return the minimum temperature supported by the thermostat."""
        if self.temperature_unit == TEMP_FAHRENHEIT:
            return AQUALINK_TEMP_FAHRENHEIT_HIGH
        return AQUALINK_TEMP_CELSIUS_HIGH

    @property
    def target_temperature(self) -> float:
        """Return the current target temperature."""
        return float(self.dev.state)

    @refresh_system
    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        await self.dev.set_temperature(int(kwargs[ATTR_TEMPERATURE]))

    @property
    def sensor(self) -> AqualinkSensor:
        """Return the sensor device for the current thermostat."""
        sensor = f"{self.name.lower()}_temp"
        return self.dev.system.devices[sensor]

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        if self.sensor.state != "":
            return float(self.sensor.state)
        return None

    @property
    def heater(self) -> AqualinkHeater:
        """Return the heater device for the current thermostat."""
        heater = f"{self.name.lower()}_heater"
        return self.dev.system.devices[heater]
