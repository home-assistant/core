"""
Support for Insteon local lights.

For more details about this platform, please refer to the documentation at

--
Example platform config
--

insteon_local:
  host: YOUR HUB IP
  username: YOUR HUB USERNAME
  password: YOUR HUB PASSWORD

--
Example platform config
--

light:
  - platform: insteon_local
    lights:
      dining_room:
        device_id: 30DA8A
        name: Dining Room
      living_room:
        device_id: 30D927
        name: Living Room

"""
from homeassistant.components.insteon_local import INSTEON_LOCAL
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)

# DEPENDENCIES = ['insteonlocal']

SUPPORT_INSTEON_LOCAL = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon local light platform."""
    #devs = []

    for key, light in config['lights'].items():
        #
        light = INSTEON_LOCAL.dimmer(light['device_id'])
        light.beep()

#
#  TODO: Adapt from existing hub component to create devices
#
# class InsteonToggleDevice(Light):
#     """An abstract Class for an Insteon node."""
#
#     def __init__(self, node):
#         """Initialize the device."""
#         self.node = node
#         self._value = 0
#
#     @property
#     def name(self):
#         """Return the the name of the node."""
#
#         return self.node.DeviceName
#
#     @property
#     def unique_id(self):
#         """Return the ID of this insteon node."""
#         return self.node.DeviceID
#
#     @property
#     def brightness(self):
#         """Return the brightness of this light between 0..255."""
#         return self._value / 100 * 255
#
#     def update(self):
#         """Update state of the sensor."""
#         resp = self.node.send_command('get_status', wait=True)
#         try:
#             self._value = resp['response']['level']
#         except KeyError:
#             pass
#
#     @property
#     def is_on(self):
#         """Return the boolean response if the node is on."""
#         return self._value != 0
#
#     @property
#     def supported_features(self):
#         """Flag supported features."""
#         return SUPPORT_INSTEON_LOCAL
#
#     def turn_on(self, **kwargs):
#         """Turn device on."""
#         if ATTR_BRIGHTNESS in kwargs:
#             self._value = kwargs[ATTR_BRIGHTNESS] / 255 * 100
#             self.node.send_command('on', self._value)
#         else:
#             self._value = 100
#             self.node.send_command('on')
#
#     def turn_off(self, **kwargs):
#         """Turn device off."""
#         self.node.send_command('off')
