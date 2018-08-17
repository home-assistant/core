"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
from ipaddress import ip_address
import aiohttp
import asyncio

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_URL,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import get_local_ip

from .config_flow import configured_hosts
from .const import DOMAIN
from .const import LOGGER as _LOGGER

_LOGGER.warning('Loading IGD')


REQUIREMENTS = ['async-upnp-client==0.12.3']
DEPENDENCIES = ['http', 'api']

CONF_LOCAL_IP = 'local_ip'
CONF_ENABLE_PORT_MAPPING = 'port_mapping'
CONF_PORTS = 'ports'
CONF_UNITS = 'unit'
CONF_HASS = 'hass'

NOTIFICATION_ID = 'igd_notification'
NOTIFICATION_TITLE = 'UPnP/IGD Setup'

IP_SERVICE = 'urn:schemas-upnp-org:service:WANIPConnection:1'  # XXX TODO: remove this

UNITS = {
    "Bytes": 1,
    "KBytes": 1024,
    "MBytes": 1024**2,
    "GBytes": 1024**3,
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.url,
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=True): cv.boolean,
        vol.Optional(CONF_UNITS, default="MBytes"): vol.In(UNITS),
        vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
        vol.Optional(CONF_PORTS):
            vol.Schema({vol.Any(CONF_HASS, cv.positive_int): cv.positive_int})
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config, *args, **kwargs):
    """Register a port mapping for Home Assistant via UPnP."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}
    configured = configured_hosts(hass)
    _LOGGER.debug('Config: %s', config)
    _LOGGER.debug('configured: %s', configured)

    igds = []
    if not igds:
        return True

    for igd_conf in igds:
        hass.async_add_job(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={
                'ssdp_url': igd_conf['ssdp_url'],
            }
        ))

    return True

    # if host is None:
    #     host = get_local_ip()
    #
    # if host == '127.0.0.1':
    #     _LOGGER.error(
    #         'Unable to determine local IP. Add it to your configuration.')
    #     return False
    #
    # url = config.get(CONF_URL)
    #
    # # build requester
    # from async_upnp_client.aiohttp import AiohttpSessionRequester
    # session = async_get_clientsession(hass)
    # requester = AiohttpSessionRequester(session, True)
    #
    # # create upnp device
    # from async_upnp_client import UpnpFactory
    # factory = UpnpFactory(requester, disable_state_variable_validation=True)
    # try:
    #     upnp_device = await factory.async_create_device(url)
    # except (asyncio.TimeoutError, aiohttp.ClientError):
    #     raise PlatformNotReady()
    #
    # # wrap with IgdDevice
    # from async_upnp_client.igd import IgdDevice
    # igd_device = IgdDevice(upnp_device, None)
    # hass.data[DATA_IGD]['device'] = igd_device
    #
    # # sensors
    # unit = config.get(CONF_UNITS)
    # hass.async_create_task(discovery.async_load_platform(
    #                        hass, 'sensor', DOMAIN, {'unit': unit}, config))
    #
    # # port mapping
    # port_mapping = config.get(CONF_ENABLE_PORT_MAPPING)
    # if not port_mapping:
    #     return True
    #
    # # determine ports
    # internal_port = hass.http.server_port
    # ports = config.get(CONF_PORTS)
    # if ports is None:
    #     ports = {CONF_HASS: internal_port}
    #
    # registered = []
    # async def register_port_mappings(event):
    #     """(Re-)register the port mapping."""
    #     from async_upnp_client import UpnpError
    #     for internal, external in ports.items():
    #         if internal == CONF_HASS:
    #             internal = internal_port
    #         try:
    #             await igd_device.async_add_port_mapping(remote_host=None,
    #                                                     external_port=external,
    #                                                     protocol='TCP',
    #                                                     internal_port=internal,
    #                                                     internal_client=ip_address(host),
    #                                                     enabled=True,
    #                                                     description='Home Assistant',
    #                                                     lease_duration=None)
    #             registered.append(external)
    #             _LOGGER.debug("external %s -> %s @ %s", external, internal, host)
    #         except UpnpError as error:
    #             _LOGGER.error(error)
    #             hass.components.persistent_notification.create(
    #                 '<b>ERROR: TCP port {} is already mapped in your router.'
    #                 '</b><br />Please disable port_mapping in the <i>upnp</i> '
    #                 'configuration section.<br />'
    #                 'You will need to restart hass after fixing.'
    #                 ''.format(external),
    #                 title=NOTIFICATION_TITLE,
    #                 notification_id=NOTIFICATION_ID)
    #
    # async def deregister_port_mappings(event):
    #     """De-register the port mapping."""
    #     tasks = [igd_device.async_delete_port_mapping(remote_host=None,
    #                                                   external_port=external,
    #                                                   protocol='TCP')
    #              for external in registered]
    #     if tasks:
    #         await asyncio.wait(tasks)
    #
    # await register_port_mappings(None)
    # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, deregister_port_mappings)
    #
    # return True


async def async_setup_entry(hass, entry):
    """Set up a bridge from a config entry."""
    _LOGGER.debug('async_setup_entry, title: %s, data: %s', entry.title, entry.data)

    # port mapping?
    # sensors

    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""


