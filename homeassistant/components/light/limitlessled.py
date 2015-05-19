"""
homeassistant.components.light.limitlessled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for LimitlessLED bulbs, also known as...

EasyBulb
AppLight
AppLamp
MiLight
LEDme
dekolight
iLight

light:
  platform: limitlessled
  host: 192.168.1.10
  group_1_name: Living Room
  group_2_name: Bedroom
  group_3_name: Office
  group_4_name: Kitchen

"""
import logging

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME
from homeassistant.components.light import ATTR_BRIGHTNESS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Gets the LimitlessLED lights. """
    try:
        import ledcontroller
    except ImportError:
        _LOGGER.exception("Error while importing dependency ledcontroller.")
        return

    led = ledcontroller.LedController(config['host'])

    lights = []
    for i in range(1, 5):
        if 'group_%d_name' % (i) in config:
            lights.append(
                LimitlessLED(
                    led,
                    i,
                    config['group_%d_name' % (i)]
                )
            )

    add_devices_callback(lights)


class LimitlessLED(ToggleEntity):
    """ Represents a LimitlessLED light """

    def __init__(self, led, group, name):
        self.led = led
        self.group = group

        # LimitlessLEDs don't report state, we have track it ourselves.
        self.led.off(self.group)

        self._name = name or DEVICE_DEFAULT_NAME
        self._state = STATE_OFF
        self._brightness = brightness

    @property
    def should_poll(self):
        """ No polling needed for a demo light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def state(self):
        """ Returns the name of the device if any. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        if self.is_on:
            return {
                ATTR_BRIGHTNESS: self._brightness,
            }

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = STATE_ON

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        self.led.set_brightness(self._brightness, self.group)

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = STATE_OFF
        self.led.off(self.group)
