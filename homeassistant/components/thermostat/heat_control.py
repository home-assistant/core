"""
Adds support for a thermostat.

Specify a start time, end time and a target temperature.
If the the current temperature is lower than the target temperature,
and the time is between start time and end time, the heater will
be turned on. Opposite if the the temperature is higher than the
target temperature the heater will be turned off.

If away mode is activated the target temperature is sat to a min
temperature (min_temp in config). The min temperature is also used
as target temperature when no other temperature is specified.

If the heater is manually turned on, the target temperature will
be sat to 100*C. Meaning
the thermostat probably will never turn off the heater.
If the heater is manually turned off, the target temperature will
be sat according to normal rules. (Based on target temperature
for given time intervals and the min temperature.)

A target temperature sat with the set_temperature function will
override all other rules for the target temperature.


Config:

[thermostat]
platform=heat_control

name = Name of thermostat

heater = entity_id for heater switch,
         must be a toggle device

target_sensor = entity_id for temperature sensor,
                target_sensor.state must be temperature

time_temp = start_time-end_time:target_temp,

min_temp = minimum temperature, used when away mode is
           active or no other temperature specified.

Example:
[thermostat]
platform=heat_control
name = Stue
heater = switch.Ovn_stue
target_sensor = tellstick_sensor.Stue_temperature
time_temp = 0700-0745:17,1500-1850:20
min_temp = 10

For the example the heater will turn on at 0700 if the temperature
is lower than 17*C away mode is false. Between 0700 and 0745 the
target temperature will be 17*C. Between 0745 and 1500 no temperature
is specified. so the min_temp of 10*C will be used. From 1500 to 1850
the target temperature is 20*, but if away mode is true the target
temperature will be sat to 10*C

"""

import logging
import datetime
import homeassistant.components as core

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELCIUS, STATE_ON, STATE_OFF

TOL_TEMP = 0.3


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the heat control thermostat. """
    logger = logging.getLogger(__name__)

    add_devices([HeatControl(hass, config, logger)])


# pylint: disable=too-many-instance-attributes
class HeatControl(ThermostatDevice):
    """ Represents a HeatControl within Home Assistant. """

    def __init__(self, hass, config, logger):

        self.logger = logger
        self.hass = hass
        self.heater_entity_id = config.get("heater")

        self.name_device = config.get("name")
        self.target_sensor_entity_id = config.get("target_sensor")

        self.time_temp = []
        for time_temp in list(config.get("time_temp").split(",")):
            time, temp = time_temp.split(':')
            time_start, time_end = time.split('-')
            start_time = datetime.datetime.time(datetime.datetime.
                                                strptime(time_start, '%H%M'))
            end_time = datetime.datetime.time(datetime.datetime.
                                              strptime(time_end, '%H%M'))
            self.time_temp.append((start_time, end_time, float(temp)))

        self.min_temp = float(config.get("min_temp"))

        self._manual_sat_temp = None
        self._away = False
        self._heater_manual_changed = True

        hass.states.track_change(self.heater_entity_id,
                                 self._heater_turned_on,
                                 STATE_OFF, STATE_ON)
        hass.states.track_change(self.heater_entity_id,
                                 self._heater_turned_off,
                                 STATE_ON, STATE_OFF)

    @property
    def name(self):
        """ Returns the name. """
        return self.name_device

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return TEMP_CELCIUS

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        target_sensor = self.hass.states.get(self.target_sensor_entity_id)
        if target_sensor:
            return float(target_sensor.state)
        else:
            return None

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        if self._manual_sat_temp:
            return self._manual_sat_temp
        elif self._away:
            return self.min_temp
        else:
            now = datetime.datetime.time(datetime.datetime.now())
            for (start_time, end_time, temp) in self.time_temp:
                if start_time < now and end_time > now:
                    return temp
            return self.min_temp

    def set_temperature(self, temperature):
        """ Set new target temperature """
        if temperature is None:
            self._manual_sat_temp = None
        else:
            self._manual_sat_temp = float(temperature)

    def update(self):
        """ Update current thermostat """
        heater = self.hass.states.get(self.heater_entity_id)
        if heater is None:
            self.logger.error("No heater available")
            return

        current_temperature = self.current_temperature
        if current_temperature is None:
            self.logger.error("No temperature available")
            return

        if (current_temperature - self.target_temperature) > \
                TOL_TEMP and heater.state is STATE_ON:
            self._heater_manual_changed = False
            core.turn_off(self.hass, self.heater_entity_id)
        elif (self.target_temperature - self.current_temperature) > TOL_TEMP \
                and heater.state is STATE_OFF:
            self._heater_manual_changed = False
            core.turn_on(self.hass, self.heater_entity_id)

    def _heater_turned_on(self, entity_id, old_state, new_state):
        """ heater is turned on"""
        if not self._heater_manual_changed:
            pass
        else:
            self.set_temperature(100)

        self._heater_manual_changed = True

    def _heater_turned_off(self, entity_id, old_state, new_state):
        """ heater is turned off"""
        if self._heater_manual_changed:
            self.set_temperature(None)

    def turn_away_mode_on(self):
        """ Turns away mode on. """
        self._away = True

    def turn_away_mode_off(self):
        """ Turns away mode off. """
        self._away = False
