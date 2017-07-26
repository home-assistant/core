import asyncio
import xknx

import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX, XKNXSwitch

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'

DEFAULT_NAME = 'XKNX Switch'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Setup the XKNX switch platform."""
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
        if isinstance(device, xknx.Switch) and \
			not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXSwitch(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import Switch
    switch = Switch(hass.data[DATA_XKNX].xknx,
                    name= \
                        config.get(CONF_NAME),
                    group_address= \
                        config.get(CONF_ADDRESS),
                    group_address_state= \
                        config.get(CONF_STATE_ADDRESS))
    switch.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(switch)
    add_devices([XKNXSwitch(hass, switch)])
