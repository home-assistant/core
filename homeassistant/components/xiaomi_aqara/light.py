"""Support for Xiaomi Gateway Light."""
import binascii
import logging
import struct

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
import homeassistant.util.color as color_util

from . import PY_XIAOMI_GATEWAY, XiaomiDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    devices = []
    for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
        for device in gateway.devices["light"]:
            model = device["model"]
            if model in ["gateway", "gateway.v3"]:
                devices.append(XiaomiGatewayLight(device, "Gateway Light", gateway))
    add_entities(devices)


class XiaomiGatewayLight(XiaomiDevice, LightEntity):
    """Representation of a XiaomiGatewayLight."""

    def __init__(self, device, name, xiaomi_hub):
        """Initialize the XiaomiGatewayLight."""
        self._data_key = "rgb"
        self._hs = (0, 0)
        self._brightness = 100

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
        if len(rgbhexstr) > 8:
            _LOGGER.error(
                "Light RGB data error."
                " Can't be more than 8 characters. Received: %s",
                rgbhexstr,
            )
            return False

        rgbhexstr = rgbhexstr.zfill(8)
        rgbhex = bytes.fromhex(rgbhexstr)
        rgba = struct.unpack("BBBB", rgbhex)
        brightness = rgba[0]
        rgb = rgba[1:]

        self._brightness = brightness
        self._hs = color_util.color_RGB_to_hs(*rgb)
        self._state = True
        return True

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(255 * self._brightness / 100)

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_HS_COLOR in kwargs:
            self._hs = kwargs[ATTR_HS_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(100 * kwargs[ATTR_BRIGHTNESS] / 255)

        rgb = color_util.color_hs_to_RGB(*self._hs)
        rgba = (self._brightness,) + rgb
        rgbhex = binascii.hexlify(struct.pack("BBBB", *rgba)).decode("ASCII")
        rgbhex = int(rgbhex, 16)

        if self._write_to_hub(self._sid, **{self._data_key: rgbhex}):
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self._write_to_hub(self._sid, **{self._data_key: 0}):
            self._state = False
            self.schedule_update_ha_state()
