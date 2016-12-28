"""
Countdown Timer component for Home Assistant https://home-assistant.io/
Documentation: https://home-assistant.io/components/sensor.countdown_timer/
Jerry Workman <jerry.workman@gmail.com>
"""

import string
import logging
from threading import Timer
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components import switch as switch
from homeassistant.helpers.entity import Entity
from homeassistant.const import (STATE_ON, STATE_UNKNOWN)
from homeassistant.helpers.event import track_state_change

_LOGGER = logging.getLogger(__name__)

DOMAIN = "countdown_timer"
ICON = "mdi:timer"
UNIT_OF_MEASUREMENT = "minutes"

CONF_SENSORS = 'sensors'
CONF_SWITCH = 'switch'
CONF_DELAY = 'delay'
DEFAULT_DELAY = 20

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
        vol.Required(CONF_SENSORS, default=None): cv.string,
        vol.Required(CONF_SWITCH, default=None): cv.string,
        vol.Optional(CONF_DELAY,
                     default=DEFAULT_DELAY): cv.positive_int,
})


def _debug(msg):
    _LOGGER.debug("%s: %s", DOMAIN, msg)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """setup cover."""
    value_template = config.get('timers', {})
    timers = []

    for dev_name, properties in value_template .items():
        _debug("Adding timed switch %s" % dev_name)
        timers.append(
            CountdownTimer(
                hass,
                dev_name,
                properties[CONF_SENSORS],
                properties[CONF_SWITCH],
                properties.get(CONF_DELAY, DEFAULT_DELAY),
            ))
    if not timers:
        _LOGGER.error("No countdown timers added. Check configuration.")
        return False

    add_devices_callback(timers)


class CountdownTimer(Entity):
    """Binary sensor(s) and a switch(light) once turned on by sensor turns off after a delay."""

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, hass, dev_name, sensors, switch_id, delay):
        self._name = dev_name
        full_name = DOMAIN + "." + dev_name
        self._full_name = full_name
        self._hass = hass
        self._sensors = sensors
        self._switch = switch_id
        self._delay = delay  # minutes
        self._count_down = 0
        self._state = 0
        self._all_entities = sensors + "," + switch_id
        self._timer = Timer(60, self.timer_timeout)  # One minute
        track_state_change(self._hass, self._sensors.split(','), self._sensor_changed)

    def _sensor_changed(self, entity, old_state, new_state):
        """ binary_sensor callback """
        _debug('%s binary sensor, new state: %s' % (self._full_name, new_state.state))
        if new_state.state == STATE_ON:
            switch.turn_on(self._hass, self._switch)
            if self._count_down > self._delay:
                # leave the timer alone if > _delay
                self._state = self._count_down
            else:
                # reset all
                self._state = self._count_down = self._delay
            self.update_ha_state()
            # self.schedule_update_ha_state()
            self._timer.cancel()
            self._timer = Timer(60, self.timer_timeout)  # One minute
            self._timer.start()

    def timer_timeout(self):
        """timed out so turn switch off"""
        self._count_down -= 1  # minute
        _debug('Tic - %d left.' % self._count_down)
        # count down in 1 minute increments for display.
        self._state = int(self._count_down)  # countdowm timer
        if self._count_down <= 0:
            self._state = 0
            _debug('Timed out')
            switch.turn_off(self._hass, self._switch)
        else:
            self._timer.cancel()  # just in case
            self._timer = Timer(60, self.timer_timeout)  # One minute
            self._timer.start()
        # self.schedule_update_ha_state()
        self.update_ha_state()

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def friendly_name(self):
        """Return friendly sensor name - has no effect ??"""
        return string.capwords(self._name.replace('_', ' '))

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return UNIT_OF_MEASUREMENT

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        return self._state

    def is_on(self):
        """Am I on?"""
        switch_state = self._hass.states.get(self._switch)
        if not switch_state:
            return STATE_UNKNOWN
        else:
            return switch_state == STATE_ON

    def update(self):
        """Update state"""
        self._state = self._count_down
        # self.schedule_update_ha_state()
        self.update_ha_state()
