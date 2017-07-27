"""
Support for KNX/IP lights via XKNX

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.xknx/
"""
import asyncio
import xknx
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX
from homeassistant.components.light import PLATFORM_SCHEMA, Light, \
    SUPPORT_BRIGHTNESS, ATTR_BRIGHTNESS
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'
CONF_BRIGHTNESS_ADDRESS = 'brightness_address'
CONF_BRIGHTNESS_STATE_ADDRESS = 'brightness_state_address'

DEFAULT_NAME = 'XKNX Light'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Set up light(s) for XKNX platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    if discovery_info is not None:
        yield from add_devices_from_component(hass, add_devices)
    else:
        yield from add_devices_from_platform(hass, config, add_devices)

    return True

@asyncio.coroutine
def add_devices_from_component(hass, add_devices):
    """Set up lights for XKNX platform configured via xknx.yaml."""
    entities = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.Light) and \
                not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXLight(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    """Set up light for XKNX platform configured within plattform."""
    from xknx import Light
    light = Light(hass.data[DATA_XKNX].xknx,
                  name= \
                      config.get(CONF_NAME),
                  group_address_switch= \
                      config.get(CONF_ADDRESS),
                  group_address_switch_state= \
                      config.get(CONF_STATE_ADDRESS),
                  group_address_brightness= \
                      config.get(CONF_BRIGHTNESS_ADDRESS),
                  group_address_brightness_state= \
                      config.get(CONF_BRIGHTNESS_STATE_ADDRESS))
    light.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(light)
    add_devices([XKNXLight(hass, light)])


class XKNXLight(Light):
    """Representation of a XKNX light."""

    def __init__(self, hass, device):
        self.device = device
        self.hass = hass
        self.register_callbacks()


    def register_callbacks(self):
        def after_update_callback(device):
            # pylint: disable=unused-argument
            self.update_ha()
        self.device.register_device_updated_cb(after_update_callback)


    def update_ha(self):
        self.hass.async_add_job(self.async_update_ha_state())


    @property
    def should_poll(self):
        """No polling needed for a demo light."""
        return False


    @property
    def name(self):
        """Return the name of the light if any."""
        return self.device.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.brightness \
            if self.device.supports_dimming else \
            None

    @property
    def xy_color(self):
        """Return the XY color value [float, float]."""
        return None

    @property
    def rgb_color(self):
        """Return the RBG color value."""
        return None

    @property
    def color_temp(self):
        """Return the CT color temperature."""
        return None

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_dimming:
            flags |= SUPPORT_BRIGHTNESS
        return flags


    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self.device.supports_dimming:
            self.device.set_brightness(int(kwargs[ATTR_BRIGHTNESS]))
        else:
            self.device.set_on()
        self.update_ha()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.device.set_off()
        self.update_ha()
