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
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, \
    CONF_HOST, CONF_PORT

DOMAIN = "xknx"
DATA_XKNX = "data_xknx"
CONF_XKNX_CONFIG = "config_file"

CONF_XKNX_ROUTING = "routing"
CONF_XKNX_TUNNELING = "tunneling"
CONF_XKNX_LOCAL_IP = "local_ip"

SUPPORTED_DOMAINS = [
    'switch',
    'climate',
    'cover',
    'light',
    'sensor',
    'binary_sensor']

_LOGGER = logging.getLogger(__name__)

#REQUIREMENTS = ['xknx==0.7.0']

TUNNELING_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Required(CONF_XKNX_LOCAL_IP): cv.string,
})

ROUTING_SCHEMA = vol.Schema({
    vol.Required(CONF_XKNX_LOCAL_IP): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_XKNX_CONFIG): cv.string,
        vol.Exclusive(CONF_XKNX_ROUTING, 'connection_type'): ROUTING_SCHEMA,
        vol.Exclusive(CONF_XKNX_TUNNELING, 'connection_type'): TUNNELING_SCHEMA,
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
        """Initialization of XKNX object."""
        from xknx import XKNX
        self.xknx = XKNX(
            config=self.config_file(),
            loop=self.hass.loop)

    @asyncio.coroutine
    def start(self):
        """Start XKNX object. Connect to tunneling or Routing device."""
        connection_config = self.connection_config()
        yield from self.xknx.start(
            state_updater=True,
            connection_config=connection_config)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.initialized = True

    @asyncio.coroutine
    def stop(self, event):
        """Stop XKNX object. Disconnect from tunneling or Routing device."""
        yield from self.xknx.stop()

    def config_file(self):
        """Resolve and return the full path of xknx.yaml if configured."""
        config_file = self.config[DOMAIN].get(CONF_XKNX_CONFIG)
        if not config_file:
            return None
        if not config_file.startswith("/"):
            return  self.hass.config.path(config_file)
        return config_file

    def connection_config(self):
        """Resolve and return the connection_config."""
        if CONF_XKNX_TUNNELING in self.config[DOMAIN]:
            return self.connection_config_tunneling()
        elif CONF_XKNX_ROUTING in self.config[DOMAIN]:
            return self.connection_config_routing()
        else:
            return self.connection_config_auto()

    def connection_config_routing(self):
        """Resolve and return the connection_config if routing is configured."""
        from xknx.io import ConnectionConfig, ConnectionType
        local_ip = \
            self.config[DOMAIN][CONF_XKNX_ROUTING].get(CONF_XKNX_LOCAL_IP)
        return ConnectionConfig(
            connection_type=ConnectionType.ROUTING,
            local_ip=local_ip)

    def connection_config_tunneling(self):
        """Resolve and return the connection_config if tunneling is configured."""
        from xknx.io import ConnectionConfig, ConnectionType, \
            DEFAULT_MCAST_PORT
        gateway_ip = \
            self.config[DOMAIN][CONF_XKNX_TUNNELING].get(CONF_HOST)
        gateway_port = \
            self.config[DOMAIN][CONF_XKNX_TUNNELING].get(CONF_PORT)
        local_ip = \
            self.config[DOMAIN][CONF_XKNX_TUNNELING].get(CONF_XKNX_LOCAL_IP)
        if gateway_port is None:
            gateway_port = DEFAULT_MCAST_PORT
        return ConnectionConfig(
            connection_type=ConnectionType.TUNNELING,
            gateway_ip=gateway_ip,
            gateway_port=gateway_port,
            local_ip=local_ip)

    def connection_config_auto(self):
        """Resolve and return the connection_config if auto is configured."""
        #pylint: disable=no-self-use
        from xknx.io import ConnectionConfig
        return ConnectionConfig()
