"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
import logging
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['miniupnpc==1.9']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'upnp'

DATA_UPNP = 'UPNP'

CONF_ENABLE_PORT_MAPPING = 'port_mapping'
CONF_UNITS = 'unit'

UNITS = {
    "Bytes": 1,
    "KBytes": 1024,
    "MBytes": 1024**2,
    "GBytes": 1024**3,
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=True): cv.boolean,
        vol.Optional(CONF_UNITS, default="MBytes"): vol.In(UNITS),
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=import-error, no-member, broad-except
def setup(hass, config):
    """Register a port mapping for Home Assistant via UPnP."""
    import miniupnpc

    upnp = miniupnpc.UPnP()
    hass.data[DATA_UPNP] = upnp

    upnp.discoverdelay = 200
    upnp.discover()
    try:
        upnp.selectigd()
    except Exception:
        _LOGGER.exception("Error when attempting to discover an UPnP IGD")
        return False

    unit = config[DOMAIN].get(CONF_UNITS)
    discovery.load_platform(hass, 'sensor', DOMAIN, {'unit': unit}, config)

    port_mapping = config[DOMAIN].get(CONF_ENABLE_PORT_MAPPING)
    if not port_mapping:
        return True

    base_url = urlsplit(hass.config.api.base_url)
    host = base_url.hostname
    external_port = internal_port = base_url.port

    upnp.addportmapping(
        external_port, 'TCP', host, internal_port, 'Home Assistant', '')

    def deregister_port(event):
        """De-register the UPnP port mapping."""
        upnp.deleteportmapping(hass.config.api.port, 'TCP')

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, deregister_port)

    return True
