"""

Connects to XKNX platform.

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
CONF_XKNX_FIRE_EVENT = "fire_event"

SERVICE_XKNX_SEND = "send"
SERVICE_XKNX_ATTR_ADDRESS = "address"
SERVICE_XKNX_ATTR_PAYLOAD = "payload"

SUPPORTED_DOMAINS = [
    'switch',
    'climate',
    'cover',
    'light',
    'sensor',
    'binary_sensor']

_LOGGER = logging.getLogger(__name__)

#REQUIREMENTS = ['xknx==0.7.6']

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
        vol.Exclusive(CONF_XKNX_TUNNELING, 'connection_type'):
            TUNNELING_SCHEMA,
        vol.Optional(CONF_XKNX_FIRE_EVENT, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_XKNX_SEND_SCHEMA = vol.Schema({
    vol.Required(SERVICE_XKNX_ATTR_ADDRESS): cv.string,
    vol.Required(SERVICE_XKNX_ATTR_PAYLOAD): vol.Any(
        cv.positive_int, [cv.positive_int]),
})


@asyncio.coroutine
def async_setup(hass, config):
    """Set up xknx component."""
    from xknx.exceptions import XKNXException
    try:
        hass.data[DATA_XKNX] = XKNXModule(hass, config)
        yield from hass.data[DATA_XKNX].start()

    except XKNXException as ex:
        _LOGGER.exception("Can't connect to KNX interface: %s", ex)
        return False

    for component in SUPPORTED_DOMAINS:
        hass.async_add_job(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config))

    hass.services.async_register(
        DOMAIN, SERVICE_XKNX_SEND,
        hass.data[DATA_XKNX].service_send_to_knx_bus,
        schema=SERVICE_XKNX_SEND_SCHEMA)

    return True


class XKNXModule(object):
    """Representation of XKNX Object."""

    def __init__(self, hass, config):
        """Initialization of XKNXModule."""
        self.hass = hass
        self.config = config
        self.initialized = False
        self.init_xknx()
        self.register_callbacks()

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
            return self.hass.config.path(config_file)
        return config_file

    def connection_config(self):
        """Return the connection_config."""
        if CONF_XKNX_TUNNELING in self.config[DOMAIN]:
            return self.connection_config_tunneling()
        elif CONF_XKNX_ROUTING in self.config[DOMAIN]:
            return self.connection_config_routing()
        else:
            return self.connection_config_auto()

    def connection_config_routing(self):
        """Return the connection_config if routing is configured."""
        from xknx.io import ConnectionConfig, ConnectionType
        local_ip = \
            self.config[DOMAIN][CONF_XKNX_ROUTING].get(CONF_XKNX_LOCAL_IP)
        return ConnectionConfig(
            connection_type=ConnectionType.ROUTING,
            local_ip=local_ip)

    def connection_config_tunneling(self):
        """Return the connection_config if tunneling is configured."""
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
        """Return the connection_config if auto is configured."""
        # pylint: disable=no-self-use
        from xknx.io import ConnectionConfig
        return ConnectionConfig()

    def register_callbacks(self):
        """Register callbacks within XKNX object."""
        if self.config[DOMAIN][CONF_XKNX_FIRE_EVENT]:
            self.xknx.telegram_queue.register_telegram_received_cb(
                self.telegram_received_cb)

    @asyncio.coroutine
    def telegram_received_cb(self, telegram):
        """Callback invoked after a KNX telegram was received."""
        self.hass.bus.fire('knx_event', {
            'address': telegram.group_address.str(),
            'data': telegram.payload.value
        })
        # False signals XKNX to proceed with processing telegrams.
        return False

    @asyncio.coroutine
    def service_send_to_knx_bus(self, call):
        """Service for sending an arbitray KNX message to the KNX bus."""
        from xknx.knx import Telegram, Address, DPTBinary, DPTArray
        attr_payload = call.data.get(SERVICE_XKNX_ATTR_PAYLOAD)
        attr_address = call.data.get(SERVICE_XKNX_ATTR_ADDRESS)

        def calculate_payload(attr_payload):
            """Calculate payload depending on type of attribute."""
            if isinstance(attr_payload, int):
                return DPTBinary(attr_payload)
            return DPTArray(attr_payload)
        payload = calculate_payload(attr_payload)
        address = Address(attr_address)

        telegram = Telegram()
        telegram.payload = payload
        telegram.group_address = address
        yield from self.xknx.telegrams.put(telegram)
