"""Support for NuHeat thermostats."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

# Hold modes
MODE_AUTO = HVAC_MODE_AUTO  # Run device schedule
MODE_HOLD_TEMPERATURE = "temperature"
MODE_TEMPORARY_HOLD = "temporary_temperature"

OPERATION_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

SCHEDULE_HOLD = 3
SCHEDULE_RUN = 1
SCHEDULE_TEMPORARY_HOLD = 2

SERVICE_RESUME_PROGRAM = "resume_program"

RESUME_PROGRAM_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NuHeat thermostat(s)."""
    if discovery_info is None:
        return

    temperature_unit = hass.config.units.temperature_unit
    api, serial_numbers = hass.data[DOMAIN]
    thermostats = [
        NuHeatThermostat(api, serial_number, temperature_unit)
        for serial_number in serial_numbers
    ]
    add_entities(thermostats, True)

    def resume_program_set_service(service):
        """Resume the program on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        if entity_id:
            target_thermostats = [
                device for device in thermostats if device.entity_id in entity_id
            ]
        else:
            target_thermostats = thermostats

        for thermostat in target_thermostats:
            thermostat.resume_program()

            thermostat.schedule_update_ha_state(True)

    hass.services.register(
        DOMAIN,
        SERVICE_RESUME_PROGRAM,
        resume_program_set_service,
        schema=RESUME_PROGRAM_SCHEMA,
    )


class NuHeatThermostat(ClimateDevice):
    """Representation of a NuHeat Thermostat."""

    def __init__(self, api, serial_number, temperature_unit):
        """Initialize the thermostat."""
        self._thermostat = api.get_thermostat(serial_number)
        self._temperature_unit = temperature_unit
        self._force_update = False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._thermostat.room

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._temperature_unit == "C":
            return TEMP_CELSIUS

        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._temperature_unit == "C":
            return self._thermostat.celsius

        return self._thermostat.fahrenheit

    @property
    def hvac_mode(self):
        """Return current operation. ie. heat, idle."""
        if self._thermostat.heating:
            return HVAC_MODE_HEAT

        return HVAC_MODE_OFF

    @property
    def min_temp(self):
        """Return the minimum supported temperature for the thermostat."""
        if self._temperature_unit == "C":
            return self._thermostat.min_celsius

        return self._thermostat.min_fahrenheit

    @property
    def max_temp(self):
        """Return the maximum supported temperature for the thermostat."""
        if self._temperature_unit == "C":
            return self._thermostat.max_celsius

        return self._thermostat.max_fahrenheit

    @property
    def target_temperature(self):
        """Return the currently programmed temperature."""
        if self._temperature_unit == "C":
            return self._thermostat.target_celsius

        return self._thermostat.target_fahrenheit

    @property
    def preset_mode(self):
        """Return current preset mode."""
        schedule_mode = self._thermostat.schedule_mode
        if schedule_mode == SCHEDULE_RUN:
            return MODE_AUTO

        if schedule_mode == SCHEDULE_HOLD:
            return MODE_HOLD_TEMPERATURE

        if schedule_mode == SCHEDULE_TEMPORARY_HOLD:
            return MODE_TEMPORARY_HOLD

        return MODE_AUTO

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_NONE, MODE_HOLD_TEMPERATURE, MODE_TEMPORARY_HOLD]

    @property
    def hvac_modes(self):
        """Return list of possible operation modes."""
        return OPERATION_LIST

    def resume_program(self):
        """Resume the thermostat's programmed schedule."""
        self._thermostat.resume_schedule()
        self._force_update = True

    def set_preset_mode(self, preset_mode):
        """Update the hold mode of the thermostat."""
        if preset_mode == PRESET_NONE:
            schedule_mode = SCHEDULE_RUN

        elif preset_mode == MODE_HOLD_TEMPERATURE:
            schedule_mode = SCHEDULE_HOLD

        elif preset_mode == MODE_TEMPORARY_HOLD:
            schedule_mode = SCHEDULE_TEMPORARY_HOLD

        self._thermostat.schedule_mode = schedule_mode
        self._force_update = True

    def set_temperature(self, **kwargs):
        """Set a new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if self._temperature_unit == "C":
            self._thermostat.target_celsius = temperature
        else:
            self._thermostat.target_fahrenheit = temperature

        _LOGGER.debug(
            "Setting NuHeat thermostat temperature to %s %s",
            temperature,
            self.temperature_unit,
        )

        self._force_update = True

    def update(self):
        """Get the latest state from the thermostat."""
        if self._force_update:
            self._throttled_update(no_throttle=True)
            self._force_update = False
        else:
            self._throttled_update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _throttled_update(self, **kwargs):
        """Get the latest state from the thermostat with a throttle."""
        self._thermostat.get_data()
