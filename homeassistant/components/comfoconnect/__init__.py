"""Support to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
import logging

from pycomfoconnect import Bridge, ComfoConnect
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "comfoconnect"

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = "comfoconnect_update_received_{}"

CONF_USER_AGENT = "user_agent"

DEFAULT_NAME = "ComfoAirQ"
DEFAULT_PIN = 0
DEFAULT_TOKEN = "00000000000000000000000000000001"
DEFAULT_USER_AGENT = "Home Assistant"

DEVICE = None

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.Length(
                    min=32, max=32, msg="invalid token"
                ),
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): cv.string,
                vol.Optional(CONF_PIN, default=DEFAULT_PIN): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ComfoConnect bridge."""

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    name = conf[CONF_NAME]
    token = conf[CONF_TOKEN]
    user_agent = conf[CONF_USER_AGENT]
    pin = conf[CONF_PIN]

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
    discovery.load_platform(hass, Platform.FAN, DOMAIN, {}, config)

    return True


class ComfoConnectBridge:
    """Representation of a ComfoConnect bridge."""

    def __init__(self, hass, bridge, name, token, friendly_name, pin):
        """Initialize the ComfoConnect bridge."""
        self.name = name
        self.hass = hass
        self.unique_id = bridge.uuid.hex()

        self.comfoconnect = ComfoConnect(
            bridge=bridge,
            local_uuid=bytes.fromhex(token),
            local_devicename=friendly_name,
            pin=pin,
        )
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
        """Notify listeners that we have received an update."""
        _LOGGER.debug("Received update for %s: %s", var, value)
        dispatcher_send(
            self.hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(var), value
        )
