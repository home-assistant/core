"""Support for Xiaomi Gateway Light."""
import logging
import struct
import binascii
from homeassistant.components.xiaomi_aqara import (PY_XIAOMI_GATEWAY,
                                                   XiaomiDevice)
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_RGB_COLOR,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_RGB_COLOR, Light)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    devices = []
    for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
        for device in gateway.devices['light']:
            model = device['model']
            if model == 'gateway':
                devices.append(XiaomiGatewayLight(device, 'Gateway Light',
                                                  gateway))
    add_devices(devices)


class XiaomiGatewayLight(XiaomiDevice, Light):
    """Representation of a XiaomiGatewayLight."""

    def __init__(self, device, name, xiaomi_hub):
        """Initialize the XiaomiGatewayLight."""
        self._data_key = 'rgb'
        self._rgb = (255, 255, 255)
        self._brightness = 180

        XiaomiDevice.__init__(self, device, name, xiaomi_hub)

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        value = data.get(self._data_key)
        if value is None:
            return False

        if value == 0:
            if self._state:
                self._state = False
            return True

        rgbhexstr = "%x" % value
        if len(rgbhexstr) == 7:
            rgbhexstr = '0' + rgbhexstr
        elif len(rgbhexstr) != 8:
            _LOGGER.error('Light RGB data error.'
                          ' Must be 8 characters. Received: %s', rgbhexstr)
            return False

        rgbhex = bytes.fromhex(rgbhexstr)
        rgba = struct.unpack('BBBB', rgbhex)
        brightness = rgba[0]
        rgb = rgba[1:]

        self._brightness = int(255 * brightness / 100)
        self._rgb = rgb
        self._state = True
        return True

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RBG color value."""
        return self._rgb

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(100 * kwargs[ATTR_BRIGHTNESS] / 255)

        rgba = (self._brightness,) + self._rgb
        rgbhex = binascii.hexlify(struct.pack('BBBB', *rgba)).decode("ASCII")
        rgbhex = int(rgbhex, 16)

        if self._write_to_hub(self._sid, **{self._data_key: rgbhex}):
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self._write_to_hub(self._sid, **{self._data_key: 0}):
            self._state = False
