"""
Platform for Ecobee Thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.ecobee/
"""
import logging

from homeassistant.components import ecobee
from homeassistant.components.thermostat import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, ThermostatDevice)
from homeassistant.const import STATE_OFF, STATE_ON, TEMP_FAHRENHEIT

DEPENDENCIES = ['ecobee']
_LOGGER = logging.getLogger(__name__)
ECOBEE_CONFIG_FILE = 'ecobee.conf'
_CONFIGURING = {}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Ecobee Thermostat Platform."""
    if discovery_info is None:
        return
    data = ecobee.NETWORK
    hold_temp = discovery_info['hold_temp']
    _LOGGER.info(
        "Loading ecobee thermostat component with hold_temp set to %s",
        hold_temp)
    add_devices(Thermostat(data, index, hold_temp)
                for index in range(len(data.ecobee.thermostats)))


class Thermostat(ThermostatDevice):
    """A thermostat class for Ecobee."""

    def __init__(self, data, thermostat_index, hold_temp):
        """Initialize the thermostat."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(
            self.thermostat_index)
        self._name = self.thermostat['name']
        self.hold_temp = hold_temp

    def update(self):
        """Get the latest state from the thermostat."""
        self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(
            self.thermostat_index)

    @property
    def name(self):
        """Return the name of the Ecobee Thermostat."""
        return self.thermostat['name']

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat['runtime']['actualTemperature'] / 10

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == 'heat' or self.hvac_mode == 'auxHeatOnly':
            return self.target_temperature_low
        elif self.hvac_mode == 'cool':
            return self.target_temperature_high
        else:
            return (self.target_temperature_low +
                    self.target_temperature_high) / 2

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        return int(self.thermostat['runtime']['desiredHeat'] / 10)

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        return int(self.thermostat['runtime']['desiredCool'] / 10)

    @property
    def humidity(self):
        """Return the current humidity."""
        return self.thermostat['runtime']['actualHumidity']

    @property
    def desired_fan_mode(self):
        """Return the desired fan mode of operation."""
        return self.thermostat['runtime']['desiredFanMode']

    @property
    def fan(self):
        """Return the current fan state."""
        if 'fan' in self.thermostat['equipmentStatus']:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        status = self.thermostat['equipmentStatus']
        if status == '':
            return STATE_IDLE
        elif 'Cool' in status:
            return STATE_COOL
        elif 'auxHeat' in status:
            return STATE_HEAT
        elif 'heatPump' in status:
            return STATE_HEAT
        else:
            return status

    @property
    def mode(self):
        """Return current mode ie. home, away, sleep."""
        return self.thermostat['program']['currentClimateRef']

    @property
    def hvac_mode(self):
        """Return current hvac mode ie. auto, auxHeatOnly, cool, heat, off."""
        return self.thermostat['settings']['hvacMode']

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        # Move these to Thermostat Device and make them global
        return {
            "humidity": self.humidity,
            "fan": self.fan,
            "mode": self.mode,
            "hvac_mode": self.hvac_mode
        }

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        mode = self.mode
        events = self.thermostat['events']
        for event in events:
            if event['running']:
                mode = event['holdClimateRef']
                break
        return 'away' in mode

    def turn_away_mode_on(self):
        """Turn away on."""
        if self.hold_temp:
            self.data.ecobee.set_climate_hold(self.thermostat_index,
                                              "away", "indefinite")
        else:
            self.data.ecobee.set_climate_hold(self.thermostat_index, "away")

    def turn_away_mode_off(self):
        """Turn away off."""
        self.data.ecobee.resume_program(self.thermostat_index)

    def set_temperature(self, temperature):
        """Set new target temperature."""
        temperature = int(temperature)
        low_temp = temperature - 1
        high_temp = temperature + 1
        if self.hold_temp:
            self.data.ecobee.set_hold_temp(self.thermostat_index, low_temp,
                                           high_temp, "indefinite")
        else:
            self.data.ecobee.set_hold_temp(self.thermostat_index, low_temp,
                                           high_temp)

    def set_hvac_mode(self, mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        self.data.ecobee.set_hvac_mode(self.thermostat_index, mode)

    # Home and Sleep mode aren't used in UI yet:

    # def turn_home_mode_on(self):
    #     """ Turns home mode on. """
    #     self.data.ecobee.set_climate_hold(self.thermostat_index, "home")

    # def turn_home_mode_off(self):
    #     """ Turns home mode off. """
    #     self.data.ecobee.resume_program(self.thermostat_index)

    # def turn_sleep_mode_on(self):
    #     """ Turns sleep mode on. """
    #     self.data.ecobee.set_climate_hold(self.thermostat_index, "sleep")

    # def turn_sleep_mode_off(self):
    #     """ Turns sleep mode off. """
    #     self.data.ecobee.resume_program(self.thermostat_index)
