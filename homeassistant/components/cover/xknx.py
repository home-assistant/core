import asyncio
import xknx
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX, XKNXCover

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_MOVE_LONG_ADDRESS = 'move_long_address'
CONF_MOVE_SHORT_ADDRESS = 'move_short_address'
CONF_POSITION_ADDRESS = 'position_address'
CONF_POSITION_STATE_ADDRESS = 'position_state_address'
CONF_TRAVELLING_TIME_DOWN = 'travelling_time_down'
CONF_TRAVELLING_TIME_UP = 'travelling_time_up'

DEFAULT_TRAVEL_TIME = 25
DEFAULT_NAME = 'XKNX Binary Sensor'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MOVE_LONG_ADDRESS): cv.string,
    vol.Optional(CONF_MOVE_SHORT_ADDRESS): cv.string,
    vol.Optional(CONF_POSITION_ADDRESS): cv.string,
    vol.Optional(CONF_POSITION_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_TRAVELLING_TIME_DOWN, default=DEFAULT_TRAVEL_TIME):
        cv.positive_int,
    vol.Optional(CONF_TRAVELLING_TIME_UP, default=DEFAULT_TRAVEL_TIME):
        cv.positive_int,
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Setup the XKNX cover platform."""
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
    entities = []
    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.Cover) and \
                not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXCover(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import Cover
    cover = Cover(hass.data[DATA_XKNX].xknx,
                  name= \
                      config.get(CONF_NAME),
                  group_address_long= \
                      config.get(CONF_MOVE_LONG_ADDRESS),
                  group_address_short= \
                      config.get(CONF_MOVE_SHORT_ADDRESS),
                  group_address_position_feedback= \
                      config.get(CONF_POSITION_STATE_ADDRESS),
                  group_address_position= \
                      config.get(CONF_POSITION_ADDRESS),
                  travel_time_down= \
                      config.get(CONF_TRAVELLING_TIME_DOWN),
                  travel_time_up= \
                      config.get(CONF_TRAVELLING_TIME_UP))

    cover.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(cover)
    add_devices([XKNXCover(hass, cover)])
