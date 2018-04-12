"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
from ipaddress import ip_address
import logging
import asyncio

import voluptuous as vol

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util import get_local_ip

REQUIREMENTS = ['pyupnp-async==0.1.0.1']
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'upnp'

DATA_UPNP = 'upnp_device'

CONF_LOCAL_IP = 'local_ip'
CONF_ENABLE_PORT_MAPPING = 'port_mapping'
CONF_PORTS = 'ports'
CONF_UNITS = 'unit'
CONF_HASS = 'hass'

NOTIFICATION_ID = 'upnp_notification'
NOTIFICATION_TITLE = 'UPnP Setup'

IGD_DEVICE = 'urn:schemas-upnp-org:device:InternetGatewayDevice:1'
PPP_SERVICE = 'urn:schemas-upnp-org:service:WANPPPConnection:1'
IP_SERVICE = 'urn:schemas-upnp-org:service:WANIPConnection:1'
CIC_SERVICE = 'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1'

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


async def async_setup(hass, config):
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

    import pyupnp_async
    from pyupnp_async.error import UpnpSoapError

    service = None
    resp = await pyupnp_async.msearch_first(search_target=IGD_DEVICE)
    if not resp:
        return False

    try:
        device = await resp.get_device()
        hass.data[DATA_UPNP] = device
        for _service in device.services:
            if _service['serviceType'] == PPP_SERVICE:
                service = device.find_first_service(PPP_SERVICE)
            if _service['serviceType'] == IP_SERVICE:
                service = device.find_first_service(IP_SERVICE)
            if _service['serviceType'] == CIC_SERVICE:
                unit = config.get(CONF_UNITS)
                discovery.load_platform(hass, 'sensor',
                                        DOMAIN,
                                        {'unit': unit},
                                        config)
    except UpnpSoapError as error:
        _LOGGER.error(error)
        return False

    if not service:
        _LOGGER.warning("Could not find any UPnP IGD")
        return False

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
            await service.add_port_mapping(internal, external, host, 'TCP',
                                           desc='Home Assistant')
            registered.append(external)
            _LOGGER.debug("external %s -> %s @ %s", external, internal, host)
        except UpnpSoapError as error:
            _LOGGER.error(error)
            hass.components.persistent_notification.create(
                '<b>ERROR: tcp port {} is already mapped in your router.'
                '</b><br />Please disable port_mapping in the <i>upnp</i> '
                'configuration section.<br />'
                'You will need to restart hass after fixing.'
                ''.format(external),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

    async def deregister_port(event):
        """De-register the UPnP port mapping."""
        tasks = [service.delete_port_mapping(external, 'TCP')
                 for external in registered]
        if tasks:
            await asyncio.wait(tasks)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, deregister_port)

    return True
