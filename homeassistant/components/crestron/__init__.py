"""Component for interacting with a Lutron RadioRA 2 system."""
import logging
import time

from cipclient import CIPSocketClient
import voluptuous as vol

from homeassistant.const import ATTR_ID, CONF_HOST, CONF_PORT
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

DOMAIN = "crestron"

_LOGGER = logging.getLogger(__name__)

CRESTRON_CONTROLLER = "crestron_controller"
CONF_IPID = "ipid"
DEFAULT_PORT = 41794

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_IPID): cv.positive_int,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CRESTRON_COMPONENTS = ["binary_sensor"]


def setup(hass, base_config):
    """Set up the Creston component."""

    hass.data[CRESTRON_CONTROLLER] = None

    config = base_config.get(DOMAIN)
    crestron = CIPSocketClient(
        config[CONF_HOST], config[CONF_IPID], config[CONF_PORT]
    )
    hass.data[CRESTRON_CONTROLLER] = crestron
    crestron.start()
    time.sleep(1.5)

    _LOGGER.info("Connected to CIP client at %s IPID %s", config[CONF_HOST], config[CONF_IPID])
    
    return True
