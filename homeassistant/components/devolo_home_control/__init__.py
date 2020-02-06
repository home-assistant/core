"""The devolo_home_control integration."""
from devolo_home_control_api.mprm_websocket import MprmWebsocket
from devolo_home_control_api.mydevolo import Mydevolo
import voluptuous as vol

from homeassistant.components import switch as ha_switch
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_MPRM, DEFAULT_MYDEVOLO, DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

#

SUPPORTED_PLATFORMS = [ha_switch.DOMAIN]

SERVER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional("mydevolo", default=DEFAULT_MYDEVOLO): cv.string,
            vol.Optional("mprm", default=DEFAULT_MPRM): cv.string,
            vol.Required("gateway"): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
        }
    )
)
CONFIG_SCHEMA = vol.Schema({DOMAIN: SERVER_CONFIG_SCHEMA}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Get all devices and add them to hass."""
    hass.data[DOMAIN] = {}
    conf = config.get(DOMAIN)
    mprm_url = conf.get("mprm")
    user = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    mydevolo = Mydevolo.get_instance()
    mydevolo.user = user
    mydevolo.password = password
    mydevolo.url = conf.get("mydevolo")
    gateway_id = mydevolo.gateway_ids[0]
    hass.data[DOMAIN]["mprm"] = MprmWebsocket(gateway_id=gateway_id, url=mprm_url)
    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)
    return True
