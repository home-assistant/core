import asyncio
import xknx
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX, XKNXClimate

from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_SETPOINT_ADDRESS = 'setpoint_address'
CONF_TEMPERATURE_ADDRESS = 'temperature_address'

DEFAULT_NAME = 'XKNX Thermostat'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SETPOINT_ADDRESS): cv.string,
    vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, \
        discovery_info=None):
    """Setup the XKNX climate platform."""
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
        if isinstance(device, xknx.Thermostat) and \
                not hasattr(device, "already_added_to_hass"):
            entities.append(XKNXClimate(hass, device))
    add_devices(entities)

@asyncio.coroutine
def add_devices_from_platform(hass, config, add_devices):
    from xknx import Thermostat
    climate = Thermostat(hass.data[DATA_XKNX].xknx,
                         name= \
                             config.get(CONF_NAME),
                         group_address_temperature= \
                             config.get(CONF_TEMPERATURE_ADDRESS),
                         group_address_setpoint= \
                             config.get(CONF_SETPOINT_ADDRESS))
    climate.already_added_to_hass = True
    hass.data[DATA_XKNX].xknx.devices.add(climate)
    add_devices([XKNXClimate(hass, climate)])
