"""Support for Toon thermostat."""

from datetime import timedelta
import logging
from typing import Any, Dict, List

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_COOL, STATE_ECO, STATE_HEAT, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import ToonDisplayDeviceEntity
from .const import DATA_TOON_CLIENT, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN

DEPENDENCIES = ['toon']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(seconds=300)

HA_TOON = {
    STATE_AUTO: 'Comfort',
    STATE_HEAT: 'Home',
    STATE_ECO: 'Away',
    STATE_COOL: 'Sleep',
}

TOON_HA = {value: key for key, value in HA_TOON.items()}


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
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_operation(self) -> str:
        """Return current operation i.e. comfort, home, away."""
        return TOON_HA.get(self._state)

    @property
    def operation_list(self) -> List[str]:
        """Return a list of available operation modes."""
        return list(HA_TOON.keys())

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float:
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

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self.toon.thermostat_state = HA_TOON[operation_mode]

    def update(self) -> None:
        """Update local state."""
        if self.toon.thermostat_state is None:
            self._state = None
        else:
            self._state = self.toon.thermostat_state.name

        self._current_temperature = self.toon.temperature
        self._target_temperature = self.toon.thermostat
        self._heating_type = self.toon.agreement.heating_type
