import logging

import voluptuous as vol

from homeassistant.components.light import Light, SUPPORT_COLOR, SUPPORT_WHITE_VALUE, ATTR_WHITE_VALUE, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, CONF_DEVICES
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ["zenggewifi==0.0.3"]

DEFAULT_NAME = "Zengge Bulb"

_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    Lights = []
    for address, device_config in config[CONF_DEVICES].items():
        Lights.append(ZenggeWifiLight(address, device_config[CONF_NAME]))
    add_entities(Lights)


class ZenggeWifiLight(Light):

    def __init__(self, host, name):
        import zenggewifi
        self._bulb = zenggewifi.ZenggeWifiBulb(host)
        self._name = name
        self.is_valid = True
        self._state = False
        self._hs_color = (0, 0)
        self._white = 0
        self._brightness = 0
        from datetime import datetime
        self.update_time = datetime.now()
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s (%s)", name, host)
            return
        self.update()

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state
    
    @property
    def hs_color(self):
        return self._hs_color
    
    @property
    def brightness(self):
        return self._brightness

    @property
    def white_value(self):
        return self._white

    @property
    def supported_features(self):
        return (SUPPORT_COLOR | SUPPORT_BRIGHTNESS | SUPPORT_WHITE_VALUE)

    @property
    def should_poll(self):
        return True
    
    @property
    def assumed_state(self):
        return False
    
    def set_rgb(self, red, green, blue):
        return self._bulb.set_rgb(red, green, blue)

    def set_white(self, white):
        return self._bulb.set_white(white)

    def turn_on(self, **kwargs):
        self._bulb.on()
        self._state = True

        hs_color = kwargs.get(ATTR_HS_COLOR)
        white = kwargs.get(ATTR_WHITE_VALUE)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if white is not None:
            self._white = white
        
        if hs_color is not None:
            self._white = 0
            self._hs_color = hs_color
        
        if brightness is not None:
            self._brightness = brightness
        
        if self._white != 0:
            self.set_white(white)
        else:
            rgb = color_util.color_hsv_to_RGB(self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100)
            self.set_rgb(*rgb)
        from datetime import datetime
        self.update_time = datetime.now()

    def turn_off(self):
        self._state = False
        self._bulb.off()

    def update(self):
        from datetime import datetime
        if (datetime.now() - self.update_time).seconds < 2:
            from time import sleep
            sleep(2)
        status = self._bulb.get_status()
        if status is False:
            return False
        self._state = status.isOn
        color = status.Color
        hsv = color_util.color_RGB_to_hsv(color.R, color.G, color.B)
        self._hs_color = hsv[:2]
        self._brightness = hsv[2] / 100 * 255
        self._white = color.W