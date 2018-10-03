import asyncio
import voluptuous as vol

from homeassistant.helpers.discovery import (async_load_platform,
                                             async_listen_platform)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import (CONF_BINARY_SENSORS, CONF_DEVICE,
                                 CONF_MONITORED_VARIABLES, CONF_NAME,
                                 CONF_SENSORS, PRECISION_HALVES,
                                 PRECISION_TENTHS, PRECISION_WHOLE)
import homeassistant.helpers.config_validation as cv

DOMAIN = 'opentherm_gw'

CONF_CLIMATE = 'climate'
CONF_FLOOR_TEMP = 'floor_temperature'
CONF_PRECISION = 'precision'

SIGNAL_OPENTHERM_GW_UPDATE = 'opentherm_gw_update'

CLIMATE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default="OpenTherm Gateway"): cv.string,
    vol.Optional(CONF_PRECISION): vol.In([PRECISION_TENTHS, PRECISION_HALVES,
                                          PRECISION_WHOLE]),
    vol.Optional(CONF_FLOOR_TEMP, default=False): cv.boolean,
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]): cv.ensure_list,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_CLIMATE, default=CLIMATE_SCHEMA({})):
            CLIMATE_SCHEMA,
        vol.Optional(CONF_SENSORS, default=SENSOR_SCHEMA({})): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS, default=SENSOR_SCHEMA({})):
            SENSOR_SCHEMA,
    }),
}, extra = vol.ALLOW_EXTRA)

REQUIREMENTS = ['pyotgw==0.1b0']

async def async_setup(hass, config):
    """Set up the OpenTherm Gateway component."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    hass.async_add_job(connect_and_subscribe, hass, conf)
    hass.async_create_task(async_load_platform(
        hass, 'climate', DOMAIN, conf.get(CONF_CLIMATE)))
    #hass.async_create_task(async_load_platform(
    #    hass, 'sensor', DOMAIN, conf.get(CONF_MONITORED_VARIABLES)))
    #hass.async_create_task(async_load_platform(
    #    hass, 'binary_sensor', DOMAIN, conf.get(CONF_MONITORED_VARIABLES)))
    return True

async def connect_and_subscribe(hass, conf):
    """Connect to serial device and subscribe report handler."""
    import pyotgw
    gateway = pyotgw.pyotgw()
    await gateway.connect(hass.loop, conf[CONF_DEVICE])

    async def handle_report(status):
        """Handle reports from the OpenTherm Gateway."""
        async_dispatcher_send(hass, SIGNAL_OPENTHERM_GW_UPDATE, status)
    gateway.subscribe(handle_report)


# class OpenThermSensor(Entity):
#     """Basic functionality for opentherm_gw sensor."""
#     