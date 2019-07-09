"""Support for Toon thermostat."""

from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT, PRESET_AWAY, PRESET_COMFORT, PRESET_HOME, PRESET_SLEEP,
    SUPPORT_PRESET_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import ToonDisplayDeviceEntity
from .const import DATA_TOON_CLIENT, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_PRESET = [PRESET_AWAY, PRESET_COMFORT, PRESET_HOME, PRESET_SLEEP]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(seconds=300)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up a Toon binary sensors based on a config entry."""
    toon = hass.data[DATA_TOON_CLIENT][entry.entry_id]
    async_add_entities([ToonThermostatDevice(toon)], True)


class ToonThermostatDevice(ToonDisplayDeviceEntity, ClimateDevice):
    """Representation of a Toon climate device."""

    def __init__(self, toon) -> None:
        """Initialize the Toon climate device."""
        self._state = None

        self._current_temperature = None
        self._target_temperature = None
        self._next_target_temperature = None

        self._heating_type = None

        super().__init__(toon, "Toon Thermostat", 'mdi:thermostat')

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return '_'.join([DOMAIN, self.toon.agreement.id, 'climate'])

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._state is not None:
            return self._state.lower()
        return None

    @property
    def preset_modes(self) -> List[str]:
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return DEFAULT_MAX_TEMP

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the current state of the burner."""
        return {
            'heating_type': self._heating_type,
        }

    def set_temperature(self, **kwargs) -> None:
        """Change the setpoint of the thermostat."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self.toon.thermostat = temperature

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode is not None:
            self.toon.thermostat_state = preset_mode

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        pass

    def update(self) -> None:
        """Update local state."""
        if self.toon.thermostat_state is None:
            self._state = None
        else:
            self._state = self.toon.thermostat_state.name

        self._current_temperature = self.toon.temperature
        self._target_temperature = self.toon.thermostat
        self._heating_type = self.toon.agreement.heating_type
