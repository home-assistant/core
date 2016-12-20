"""
Tilt Switch
custom component for Home Assistant https://home-assistant.io/
Documentation: https://home-assistant.io/components/switch.tilt/
Jerry Workman <jerry.workman@gmail.com>
"""

from threading import Timer
from homeassistant.components.switch import SwitchDevice
from homeassistant.components import switch
from homeassistant.const import (STATE_ON, STATE_OFF)
# from homeassistant.components.switch import PLATFORM_SCHEMA
# import voluptuous as vol
# import homeassistant.helpers.config_validation as cv
import logging
import pprint
_LOGGER = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)

DOMAIN = 'switch.tilt'
CONF_TILT_SENSOR = 'tilt_sensor'
CONF_SWITCH = 'switch'
CONF_CONTACT_DELAY = 'contact_delay'
CONF_CONTACT_RUN_TIME = 'run_time'
DEFAULT_CONTACT_DELAY = 1  # momentary contact relay switch on time (sec)
DEFAULT_RUN_TIME = 10      # seconds required for door to open or close

"""
Not using vol because I don't know how to apply it to multiple devices
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
        vol.Required(CONF_TILT_SENSOR, default=None): cv.string,
        vol.Required(CONF_SWITCH, default=None): cv.string,
        vol.Optional(CONF_CONTACT_DELAY, default=DEFAULT_CONTACT_DELAY): cv.positive_int,
        vol.Optional(CONF_CONTACT_RUN_TIME, default=DEFAULT_RUN_TIME): cv.positive_int,
})
"""


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Add all tilt sensors."""
    _LOGGER.debug("CONFIG: %s", pp.pformat(config))
    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        _LOGGER.debug("Adding switch %s: %s, %s", dev_name, properties.get(CONF_TILT_SENSOR),
                      properties.get(CONF_SWITCH))
        devices.append(
            TiltSwitch(
                hass,
                dev_name,
                properties.get(CONF_TILT_SENSOR),
                properties.get(CONF_SWITCH),
                properties.get(CONF_CONTACT_DELAY, DEFAULT_CONTACT_DELAY),
                properties.get(CONF_CONTACT_RUN_TIME, DEFAULT_RUN_TIME)),
            )
    add_entities(devices)


class TiltSwitch(SwitchDevice):
    """
    Tilt sensor and (toggle) switch to control a garage door opener or
    motorized gate.
    """

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, hass, dev_name, tilt_sensor_id, switch_id,
                 contact_delay=DEFAULT_CONTACT_DELAY,
                 run_time=DEFAULT_RUN_TIME):
        """init the class"""
        self._name = dev_name
        self._hass = hass
        self._tilt_sensor = tilt_sensor_id
        self._switch = switch_id
        self._contact_delay = contact_delay
        self._run_time = run_time
        self._state = STATE_OFF  # Assume closed
        self._running = False  # is door in the process of opening or closing
        self._delay_timer = None
        self._run_timer = None

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def is_on(self):
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Open garage door."""
        _LOGGER.debug('tilt trying to open %s', self._name)
        if not self.is_on:
            _LOGGER.debug('tilt opening %s', self._name)
            self._toggle()
        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Close garage door."""
        _LOGGER.debug('tilt trying to close %s', self._name)
        if self.is_on:
            _LOGGER.debug('closing %s', self._name)
            self._toggle()
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    def _insure_relay_is_off(self):
        """in case that the relay is stuck on turn it off"""
        # self.hass.states.set(self._switch, STATE_OFF)
        switch.turn_off(self.hass, self._switch)  # more intuitive

    def _toggle(self):
        """Simulate a momentary contact button press."""

        def _stop_delay_timer():
            """Open momentary relay switch"""
            switch.turn_off(self.hass, self._switch)

        def _stop_run_timer():
            """The door should be open/closed by now so update state"""
            _LOGGER.debug('tilt switch %s stopping timer', self._name)
            self._running = False
            self._insure_relay_is_off()

        _LOGGER.debug("switch.turn_on %s", self._switch)
        switch.turn_on(self.hass, self._switch)
        self._running = True
        self._delay_timer = Timer(self._contact_delay, _stop_delay_timer)
        self._delay_timer.start()
        self._run_timer = Timer(self._run_time, _stop_run_timer)
        self._run_timer.start()

    def update(self):
        """Copy state of tilt sensor state of device."""
        if self._running:
            _LOGGER.debug('tilt switch %s running, assumed state is %s',
                          self._name, self._state)
        else:
            _LOGGER.debug('updating, tilt sensor is %s', self._tilt_sensor)
            tilt = self._hass.states.get(self._tilt_sensor)
            _LOGGER.debug('tilt switch %s is %s', self._name, tilt)
            self._state = tilt.state
