"""
Tilt Cover
Cover component for Home Assistant https://home-assistant.io/
Documentation: https://home-assistant.io/components/cover.tilt/
Jerry Workman <jerry.workman@gmail.com>
"""


from threading import Timer
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import CoverDevice
from homeassistant.components.cover import PLATFORM_SCHEMA
from homeassistant.components import switch
from homeassistant.const import (STATE_OPEN, STATE_CLOSED, STATE_ON, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

CONF_TILT_SENSOR = 'tilt_sensor'
CONF_SWITCH = 'switch'
CONF_CONTACT_DELAY = 'contact_delay'
CONF_CONTACT_RUN_TIME = 'run_time'
DEFAULT_CONTACT_DELAY = 1  # momentary contact relay switch on time (sec)
DEFAULT_RUN_TIME = 10      # seconds required for door to open or close

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TILT_SENSOR, default=None): cv.string,
    vol.Required(CONF_SWITCH, default=None): cv.string,
    vol.Optional(CONF_CONTACT_DELAY, default=DEFAULT_CONTACT_DELAY):
        cv.positive_int,
    vol.Optional(CONF_CONTACT_RUN_TIME, default=DEFAULT_RUN_TIME):
        cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Add all tilt sensors."""
    covers = config.get('covers', {})
    devices = []

    for dev_name, properties in covers.items():
        _LOGGER.debug("Adding cover %s: %s, %s", dev_name,
                      properties.get(CONF_TILT_SENSOR),
                      properties.get(CONF_SWITCH))
        devices.append(
            TiltCover(
                hass,
                dev_name,
                properties.get(CONF_TILT_SENSOR),
                properties.get(CONF_SWITCH),
                properties.get(CONF_CONTACT_DELAY, DEFAULT_CONTACT_DELAY),
                properties.get(CONF_CONTACT_RUN_TIME, DEFAULT_RUN_TIME)),
            )

    if not devices:
        _LOGGER.error("No covers added")
        return False

    add_entities(devices)

class TiltCover(CoverDevice):
    """
    Tilt sensor and (toggle) switch to control a garage door opener or
    motorized gate.
    """

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
        self._state = STATE_UNKNOWN
        self._running = False  # is door in the process of opening or closing
        self._delay_timer = None
        self._run_timer = None

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    @property
    def is_closed(self):
        return self._state == STATE_CLOSED

    def open_cover(self, **kwargs):
        """Open garage door."""
        if self.is_closed:
            self._toggle()
        self._state = STATE_OPEN
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs):
        """Close garage door."""
        if not self.is_closed:
            self._toggle()
        self._state = STATE_CLOSED
        self.schedule_update_ha_state()

    def _insure_relay_is_off(self):
        """
        Just in case the relay is stuck on (closed) turn it off.
        If the relay is stuck in the on (closed) position then the garage
        door opener will not work manually or via remote.
        """
        switch.turn_off(self.hass, self._switch)

    def _toggle(self):
        """Simulate a momentary contact button press."""

        def _stop_delay_timer():
            """Open momentary relay switch"""
            switch.turn_off(self.hass, self._switch)

        def _stop_run_timer():
            """The door should be open/closed by now"""
            self._running = False
            self._insure_relay_is_off()

        switch.turn_on(self.hass, self._switch)
        self._running = True
        self._delay_timer = Timer(self._contact_delay, _stop_delay_timer)
        self._delay_timer.start()
        self._run_timer = Timer(self._run_time, _stop_run_timer)
        self._run_timer.start()

    @property
    def state(self):
        return self._state

    def update(self):
        """Copy state of tilt sensor state of device."""
        if self._running:
            _LOGGER.debug('tilt switch %s running, assumed state is %s',
                          self._name, self._state)
        else:
            tilt = self._hass.states.get(self._tilt_sensor)
            self._state = \
                STATE_OPEN if tilt.state == STATE_ON else STATE_CLOSED
