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

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.components.light import Light, ATTR_BRIGHTNESS

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['ledcontroller>=1.0.7']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Gets the LimitlessLED lights. """
    import ledcontroller

    led = ledcontroller.LedController(config['host'])

    lights = []
    for i in range(1, 5):
        if 'group_%d_name' % (i) in config:
            lights.append(LimitlessLED(led, i, config['group_%d_name' % (i)]))

    add_devices_callback(lights)


class LimitlessLED(Light):
    """ Represents a LimitlessLED light """

    def __init__(self, led, group, name):
        self.led = led
        self.group = group

        # LimitlessLEDs don't report state, we have track it ourselves.
        self.led.off(self.group)

        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False
        self._brightness = 100

    @property
    def should_poll(self):
        """ No polling needed for a demo light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def brightness(self):
        return self._brightness

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        self.led.set_brightness(self._brightness, self.group)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self.led.off(self.group)
        self.update_ha_state()
