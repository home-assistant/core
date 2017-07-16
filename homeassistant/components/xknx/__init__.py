"""

Connects to XKNX platform

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xknx/

"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .xknx_binary_sensor import XKNXBinarySensor
from .xknx_sensor import XKNXSensor
from .xknx_switch import XKNXSwitch
from .xknx_climate import XKNXClimate
from .xknx_cover import XKNXCover
from .xknx_light import XKNXLight

DOMAIN = "xknx"
DATA_XKNX = "data_xknx"
CONF_XKNX_CONFIG= "config_file"
SUPPORTED_DOMAINS = [
    'switch',
    'climate',
    'cover',
    'light',
    'sensor',
    'binary_sensor']

_LOGGER = logging.getLogger(__name__)

#REQUIREMENTS = ['xknx==0.5.0']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_XKNX_CONFIG): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

@asyncio.coroutine
def async_setup(hass, config):
    """Setup xknx component."""

    from xknx import XKNXException
    try:
        hass.data[DATA_XKNX] = XKNXModule(hass, config)
        yield from hass.data[DATA_XKNX].start()

    except XKNXException as ex:
        _LOGGER.exception("Can't connect to KNX interface: %s", ex)
        return False

    for component in SUPPORTED_DOMAINS:
        hass.async_add_job(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config))

    return True


class XKNXModule(object):
    """Representation of XKNX Object."""

    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.initialized = False
        self.init_xknx()

    def init_xknx(self):
        from xknx import XKNX
        self.xknx = XKNX(
            config=self.config_file(),
            loop=self.hass.loop,
            start=False)

    @staticmethod
    def telegram_received_callback(xknx, device):
        #print("{0}".format(device.name))
        pass

    @asyncio.coroutine
    def start(self):

        yield from self.xknx.async_start(
            state_updater=True,
            telegram_received_callback=self.telegram_received_callback)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.initialized = True

    @asyncio.coroutine
    def stop(self, event):
        yield from self.xknx.async_stop()


    def config_file(self):
        config_file = self.config[DOMAIN].get(CONF_XKNX_CONFIG)
        if not config_file.startswith("/"):
            return  self.hass.config.path(config_file)
        return config_file
