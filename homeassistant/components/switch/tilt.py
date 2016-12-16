"""
Tilt Switch
custom component for Home Assistant https://home-assistant.io/
Documentation: https://home-assistant.io/components/switch.tilt/
Jerry Workman <jerry.workman@gmail.com>
"""

import time
from threading import Timer
import logging
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (STATE_ON, STATE_OFF)
import homeassistant.components as core

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'tilt'
DEFAULT_CONTACT_DELAY = 1  # relay switch on time in seconds
DEFAULT_RUN_TIME = 10      # seconds required for door to open or close


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add all tilt sensors."""
    switches = config.get('switches', {})
    devices = []

    for dev_name, properties in switches.items():
        _LOGGER.debug("Adding switch %s", dev_name)
        devices.append(
            TiltSwitch(
                hass,
                dev_name,
                properties['tilt_sensor'],
                properties['switch'],
                properties.get('contact_delay', DEFAULT_CONTACT_DELAY),
                properties.get('run_time', DEFAULT_RUN_TIME),
            ))
    add_devices_callback(devices)


class TiltSwitch(SwitchDevice):
    """
    Tilt sensor and (toggle) switch to control a garage door opener or
    motorized gate.
    """

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, hass, dev_name, tilt_sensor, switch,
                 contact_delay=DEFAULT_CONTACT_DELAY,
                 run_time=DEFAULT_RUN_TIME):
        """init the class"""
        self._name = dev_name
        self._hass = hass
        self._tilt_sensor = tilt_sensor
        self._switch = switch
        self._contact_delay = contact_delay
        self._run_time = run_time
        self._state = None
        self._running = False  # is door in the process of opening or closing
        self._timer = None
        self._insure_relay_is_off()
        self.update()

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    def _get_state(self):
        """@:returns HA state for binary_sensor (On or Off)"""
        tilt = self._hass.states.get(self._tilt_sensor)
        try:
            _LOGGER.debug('tilt _get_state %s is %s', self._name, tilt.state)
        except AttributeError:
            pass
        if tilt:
            return tilt.state
        else:
            return None

    def _insure_relay_is_off(self):
        """in case that the relay is stuck on turn it off"""
        core.turn_off(self._hass, self._switch)

    def update(self):
        """Update state of device."""
        if self._running:
            _LOGGER.debug('tilt switch %s running, assumed state is %s',
                          self._name, self._state)
            return self._state
        else:
            tilt = self._get_state()  # on or off
            _LOGGER.debug('tilt switch %s is %s', self._name, tilt)

    @property
    def is_on(self):
        """@:returns True if on"""
        return True if self._state == STATE_ON else False

    def toggle(self):
        """Simulate a momentary contact button press."""

        def _stop_timer():
            """The door should be open/closed by now so update state"""
            _LOGGER.debug('tilt switch %s stopping timer', self._name)
            self._running = False
            self._insure_relay_is_off()
            self._state = self._get_state()

        core.turn_on(self._hass, self._switch)
        self._running = True
        time.sleep(self._contact_delay)
        core.turn_off(self._hass, self._switch)
        self._timer = Timer(self._run_time, _stop_timer)
        self._timer.start()

    def turn_on(self, **kwargs):
        """Open garage door."""
        if not self.is_on:
            _LOGGER.debug('tilt opening %s', self._name)
            self.toggle()
        self._state = STATE_ON
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Close garage door."""
        if self.is_on:
            _LOGGER.debug('closing %s', self._name)
            self.toggle()
        self._state = STATE_OFF
        self.update_ha_state()
