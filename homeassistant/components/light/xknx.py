import asyncio
import xknx
import voluptuous as vol

from homeassistant.components.xknx import _LOGGER, DATA_XKNX, \
    XKNXLight

from homeassistant.components.light import PLATFORM_SCHEMA
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
    """Setup the demo light platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    if discovery_info is not None:
        yield from add_devices_from_component(hass, add_devices)
        return True

    else:
        yield from add_devices_from_platform(hass, config, add_devices)
        return True

@asyncio.coroutine
def add_devices_from_component(hass, add_devices):
    entities = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.Light) and \
            not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXLight(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import Light
    light = Light(hass.data[DATA_XKNX].xknx,
                  name= \
                      config.get(CONF_NAME),
                  group_address_switch= \
                      config.get(CONF_ADDRESS),
                  group_address_state= \
                      config.get(CONF_STATE_ADDRESS),
                  group_address_brightness= \
                      config.get(CONF_BRIGHTNESS_ADDRESS),
                  group_address_brightness_state= \
                      config.get(CONF_BRIGHTNESS_STATE_ADDRESS))
    light.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(light)
    add_devices([XKNXLight(hass, light)])
