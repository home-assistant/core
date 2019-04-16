"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PIN, CONF_TOKEN, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'comfoconnect'

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = 'comfoconnect_update_received'

ATTR_CURRENT_TEMPERATURE = 'current_temperature'
ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_OUTSIDE_TEMPERATURE = 'outside_temperature'
ATTR_OUTSIDE_HUMIDITY = 'outside_humidity'
ATTR_AIR_FLOW_SUPPLY = 'air_flow_supply'
ATTR_AIR_FLOW_EXHAUST = 'air_flow_exhaust'

CONF_USER_AGENT = 'user_agent'

DEFAULT_NAME = 'ComfoAirQ'
DEFAULT_PIN = 0
DEFAULT_TOKEN = '00000000000000000000000000000001'
DEFAULT_USER_AGENT = 'Home Assistant'

DEVICE = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN):
            vol.Length(min=32, max=32, msg='invalid token'),
        vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): cv.string,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ComfoConnect bridge."""
    from pycomfoconnect import (Bridge)

    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    name = conf.get(CONF_NAME)
    token = conf.get(CONF_TOKEN)
    user_agent = conf.get(CONF_USER_AGENT)
    pin = conf.get(CONF_PIN)

    # Run discovery on the configured ip
    bridges = Bridge.discover(host)
    if not bridges:
        _LOGGER.error("Could not connect to ComfoConnect bridge on %s", host)
        return False
    bridge = bridges[0]
    _LOGGER.info("Bridge found: %s (%s)", bridge.uuid.hex(), bridge.host)

    # Setup ComfoConnect Bridge
    ccb = ComfoConnectBridge(hass, bridge, name, token, user_agent, pin)
    hass.data[DOMAIN] = ccb

    # Start connection with bridge
    ccb.connect()

    # Schedule disconnect on shutdown
    def _shutdown(_event):
        ccb.disconnect()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    # Load platforms
    discovery.load_platform(hass, 'fan', DOMAIN, {}, config)

    return True


class ComfoConnectBridge:
    """Representation of a ComfoConnect bridge."""

    def __init__(self, hass, bridge, name, token, friendly_name, pin):
        """Initialize the ComfoConnect bridge."""
        from pycomfoconnect import (ComfoConnect)

        self.data = {}
        self.name = name
        self.hass = hass

        self.comfoconnect = ComfoConnect(
            bridge=bridge, local_uuid=bytes.fromhex(token),
            local_devicename=friendly_name, pin=pin)
        self.comfoconnect.callback_sensor = self.sensor_callback

    def connect(self):
        """Connect with the bridge."""
        _LOGGER.debug("Connecting with bridge")
        self.comfoconnect.connect(True)

    def disconnect(self):
        """Disconnect from the bridge."""
        _LOGGER.debug("Disconnecting from bridge")
        self.comfoconnect.disconnect()

    def sensor_callback(self, var, value):
        """Call function for sensor updates."""
        _LOGGER.debug("Got value from bridge: %d = %d", var, value)

        from pycomfoconnect import (
            SENSOR_TEMPERATURE_EXTRACT, SENSOR_TEMPERATURE_OUTDOOR)

        if var in [SENSOR_TEMPERATURE_EXTRACT, SENSOR_TEMPERATURE_OUTDOOR]:
            self.data[var] = value / 10
        else:
            self.data[var] = value

        # Notify listeners that we have received an update
        dispatcher_send(self.hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, var)

    def subscribe_sensor(self, sensor_id):
        """Subscribe for the specified sensor."""
        self.comfoconnect.register_sensor(sensor_id)
