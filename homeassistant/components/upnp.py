"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
from ipaddress import ip_address
import logging

import voluptuous as vol

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util import get_local_ip

REQUIREMENTS = ['miniupnpc==2.0.2']
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'upnp'

DATA_UPNP = 'UPNP'

CONF_LOCAL_IP = 'local_ip'
CONF_ENABLE_PORT_MAPPING = 'port_mapping'
CONF_PORTS = 'ports'
CONF_UNITS = 'unit'
CONF_HASS = 'hass'

NOTIFICATION_ID = 'upnp_notification'
NOTIFICATION_TITLE = 'UPnP Setup'

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
        vol.Optional(CONF_LOCAL_IP): ip_address,
        vol.Optional(CONF_PORTS):
            vol.Schema({vol.Any(CONF_HASS, cv.positive_int): cv.positive_int})
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=import-error, no-member, broad-except, c-extension-no-member
def setup(hass, config):
    """Register a port mapping for Home Assistant via UPnP."""
    config = config[DOMAIN]
    host = config.get(CONF_LOCAL_IP)

    if host is not None:
        host = str(host)
    else:
        host = get_local_ip()

    if host == '127.0.0.1':
        _LOGGER.error(
            'Unable to determine local IP. Add it to your configuration.')
        return False

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

    unit = config.get(CONF_UNITS)
    discovery.load_platform(hass, 'sensor', DOMAIN, {'unit': unit}, config)

    port_mapping = config.get(CONF_ENABLE_PORT_MAPPING)
    if not port_mapping:
        return True

    internal_port = hass.http.server_port

    ports = config.get(CONF_PORTS)
    if ports is None:
        ports = {CONF_HASS: internal_port}

    registered = []
    for internal, external in ports.items():
        if internal == CONF_HASS:
            internal = internal_port
        try:
            upnp.addportmapping(
                external, 'TCP', host, internal, 'Home Assistant', '')
            registered.append(external)
        except Exception:
            _LOGGER.exception("UPnP failed to configure port mapping for %s",
                              external)
            hass.components.persistent_notification.create(
                '<b>ERROR: tcp port {} is already mapped in your router.'
                '</b><br />Please disable port_mapping in the <i>upnp</i> '
                'configuration section.<br />'
                'You will need to restart hass after fixing.'
                ''.format(external),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

    def deregister_port(event):
        """De-register the UPnP port mapping."""
        for external in registered:
            upnp.deleteportmapping(external, 'TCP')

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, deregister_port)

    return True
