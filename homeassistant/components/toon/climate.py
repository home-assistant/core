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

from . import ToonEntity
from .const import DATA_TOON_CLIENT, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN

DEPENDENCIES = ['toon']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCAN_INTERVAL = timedelta(minutes=30)

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


class ToonThermostatDevice(ToonEntity, ClimateDevice):
    """Representation of a Toon climate device."""

    def __init__(self, toon) -> None:
        """Initialize the Toon climate device."""
        self._state = None

        self._current_temperature = None
        self._target_temperature = None
        self._next_target_temperature = None
        self._modulation_level = None

        self._heating_type = None
        self._program_state = None
        self._program_next = None
        self._holiday_state = None

        super().__init__(toon, "Toon Thermostat", 'mdi:thermostat')

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return self.toon.agreement.id

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this thermostat."""
        agreement = self.toon.agreement
        model = agreement.display_hardware_version.rpartition('/')[0]
        sw_version = agreement.display_software_version.rpartition('/')[-1]
        return {
            'identifiers': {
                (DOMAIN, agreement.id)
            },
            'name': self._name,
            'manufacturer': 'Eneco',
            'model': model,
            'sw_version': sw_version,
        }

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
    def min_temp(self):
        """Return the minimum temperature."""
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return DEFAULT_MAX_TEMP

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the current state of the burner."""
        return {
            'heating_type': self._heating_type,

            'next_target_temperature': self._next_target_temperature,
            'modulation_level': self._modulation_level,

            'program_state': self._program_state,
            'program_next': self._program_next,
            'holiday_state': self._holiday_state,
        }

    def set_temperature(self, **kwargs) -> None:
        """Change the setpoint of the thermostat."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self.toon.thermostat = temperature

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self.toon.thermostat_state = HA_TOON[operation_mode]

    async def async_update(self) -> None:
        """Update local state."""
        thermostat = self.toon.thermostat_info

        if self.toon.thermostat_state is None:
            self._state = None
        else:
            self._state = self.toon.thermostat_state.name

        self._current_temperature = self.toon.temperature
        self._target_temperature = self.toon.thermostat
        self._next_target_temperature = thermostat.next_set_point / 100.0
        self._modulation_level = thermostat.current_modulation_level

        self._heating_type = self.toon.agreement.heating_type
        self._program_state = thermostat.program_state
        self._program_next = thermostat.next_program
        self._holiday_state = (thermostat.active_state == 4)
