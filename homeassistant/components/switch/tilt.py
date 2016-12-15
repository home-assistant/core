"""
Tilt switch.

Jerry Workman <jerry.workman@gmail.com>
License: MIT
5 Nov 2016

Combines a tilt sensor and a relay switch to control a garage door opener or motorized gate.
When this switch is turned on it will toggle the relay to activate the garage door if it is
not already open. The reverse will happen when it is turned off.

The status is not reported while the door is opening or closing based on the run_time parameter.

My Hardware:
Ecolink Intelligent Technology Z-Wave Garage Door Tilt Sensor: http://amzn.to/2ebYPgU
GoControl Z-Wave Isolated Contact Fixture Module - FS20Z-1: http://amzn.to/2ec29bK

Copy this file to <config_dir>/switch/tilt.py
Add the following to your configuration.yaml:

switch tilt:
  platform: tilt
  switches:
    front_garage_door:
      tilt_sensor:   binary_sensor.my_tilt_switch
      switch:        switch.my_relay_switch
      contact_delay: 1  #optional on time for switch to simulate button press. default: 1 second
      run_time:      10 #optional run time for the opener. default: 10 seconds
"""

import time
from threading import Timer
import logging
from homeassistant.components.switch import SwitchDevice
#from homeassistant.components import is_on, turn_on, turn_off
import homeassistant.components as core

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'tilt'
DEFAULT_CONTACT_DELAY = 1  #relay switch on time in seconds
DEFAULT_RUN_TIME = 10      #seconds required for door to open or close

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
    """Tilt sensor and (toggle) switch to control a garage door opener or motorized gate."""

    # pylint: disable=too-many-instance-attributes,too-many-arguments

    def __init__(self, hass, dev_name, tilt_sensor, switch,
                 contact_delay=DEFAULT_CONTACT_DELAY, run_time=DEFAULT_RUN_TIME):
        self._name = dev_name
        self._hass = hass
        self._tilt_sensor = tilt_sensor
        self._switch = switch
        self._contact_delay = contact_delay
        self._run_time = run_time
        self._state = None
        self._running = False    # is door / gate in the process of opening or closing
        self._timer = None
        self.update()

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    def _get_state(self):
        tilt = self._hass.states.get(self._tilt_sensor)
        try:
            _LOGGER.debug('tilt _get_state %s is %s', self._name, tilt.state)
        except AttributeError:
            pass
        if tilt:
            return tilt.state
        else:
            return None

    def _is_on(self):
        """tilt = True then garage door is open."""
        if self._running:
            _LOGGER.debug('tilt switch %s running, assumed state is %s', self._name, self._state)
            return self._state
        tilt = self._get_state() #on or off
        _LOGGER.debug('tilt switch %s is %s', self._name, tilt)
        if tilt:
            return tilt.lower() == 'on'
        else:
            return None

    @property
    def is_on(self):
        return self._is_on()

    def toggle(self):
        """Simulate a momentary contact button press."""
        def _stop_timer():
            _LOGGER.debug('tilt switch %s stopping timer', self._name)
            self._running = False

        core.turn_on(self._hass, self._switch)
        self._running = True
        time.sleep(self._contact_delay)
        core.turn_off(self._hass, self._switch)
        self._timer = Timer(self._run_time, _stop_timer)
        self._timer.start()

    def turn_on(self, **kwargs):
        """Open garage door."""
        if not self._is_on():
            _LOGGER.debug('tilt opening %s', self._name)
            self.toggle()
        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Close garage door."""
        if self._is_on():
            _LOGGER.debug('closing %s', self._name)
            self.toggle()
        self._state = False
        self.update_ha_state()

    def update(self):
        self._state = self._is_on()
