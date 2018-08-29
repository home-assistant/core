"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
# XXX TODO:
# + flow:
#   + discovery
#   + adding device
#   + removing device
# - configured:
#   - adding
# - sensors:
#   + adding
#   + handle overflow
#   - removing
# - port forward:
#   - adding
#   - removing
#   - shutdown


from ipaddress import IPv4Address
from ipaddress import ip_address
import aiohttp
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.const import CONF_URL
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import get_local_ip

from .config_flow import configured_udns
from .const import CONF_PORT_FORWARD, CONF_SENSORS
from .const import DOMAIN
from .const import LOGGER as _LOGGER


REQUIREMENTS = ['async-upnp-client==0.12.4']
DEPENDENCIES = ['http']

CONF_LOCAL_IP = 'local_ip'
CONF_ENABLE_PORT_MAPPING = 'port_mapping'
CONF_PORTS = 'ports'
CONF_UNITS = 'unit'
CONF_HASS = 'hass'

NOTIFICATION_ID = 'igd_notification'
NOTIFICATION_TITLE = 'UPnP/IGD Setup'

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


async def _async_create_igd_device(hass: HomeAssistantType, ssdp_description: str):
    """."""
    # build requester
    from async_upnp_client.aiohttp import AiohttpSessionRequester
    session = async_get_clientsession(hass)
    requester = AiohttpSessionRequester(session, True)

    # create upnp device
    from async_upnp_client import UpnpFactory
    factory = UpnpFactory(requester, disable_state_variable_validation=True)
    try:
        upnp_device = await factory.async_create_device(ssdp_description)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    # wrap with IgdDevice
    from async_upnp_client.igd import IgdDevice
    igd_device = IgdDevice(upnp_device, None)
    return igd_device


def _store_device(hass: HomeAssistantType, udn, igd_device):
    """Store an igd_device by udn."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN]['devices'] = hass.data[DOMAIN].get('devices', {})
    hass.data[DOMAIN]['devices'][udn] = igd_device


def _get_device(hass: HomeAssistantType, udn):
    """Get an igd_device by udn."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN]['devices'] = hass.data[DOMAIN].get('devices', {})
    return hass.data[DOMAIN]['devices'][udn]


async def _async_create_port_forward(hass: HomeAssistantType, igd_device):
    """Create a port forward."""
    _LOGGER.debug('Creating port forward: %s', igd_device)

    # determine local ip, ensure sane IP
    local_ip = get_local_ip()
    if local_ip == '127.0.0.1':
        _LOGGER.warning('Could not create port forward, our IP is 127.0.0.1')
        return False
    local_ip = IPv4Address(local_ip)

    # create port mapping
    port = hass.http.server_port
    await igd_device.async_add_port_mapping(remote_host=None,
                                            external_port=port,
                                            protocol='TCP',
                                            internal_port=port,
                                            internal_client=local_ip,
                                            enabled=True,
                                            description="Home Assistant",
                                            lease_duration=None)

    return True


async def _async_remove_port_forward(hass: HomeAssistantType, igd_device):
    """Remove a port forward."""
    _LOGGER.debug('Removing port forward: %s', igd_device)

    # remove port mapping
    port = hass.http.server_port
    await igd_device.async_remove_port_mapping(remote_host=None,
                                               external_port=port,
                                               protocol='TCP')


# config
async def async_setup(hass: HomeAssistantType, config):
    """Register a port mapping for Home Assistant via UPnP."""
    _LOGGER.debug('async_setup: config: %s', config)
    conf = config.get(DOMAIN, {})

    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    configured = configured_udns(hass)
    _LOGGER.debug('configured: %s', configured)

    # if no ssdp given: take any discovered - by flow - IGD entry
    #                   if none discovered, raise PlatformNotReady
    # if    ssdp given: use the SSDP

    igds = []  # XXX TODO
    for igd_conf in igds:
        hass.async_add_job(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={
                'ssdp_description': igd_conf['ssdp_description'],
            }
        ))

    return True


# config flow
async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Set up a bridge from a config entry."""
    _LOGGER.debug('async_setup_entry: title: %s, data: %s', config_entry.title, config_entry.data)

    data = config_entry.data
    ssdp_description = data['ssdp_description']

    # build IGD device
    try:
        igd_device = await _async_create_igd_device(hass, ssdp_description)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    _store_device(hass, igd_device.udn, igd_device)

    # port forward
    if data.get(CONF_PORT_FORWARD):
        await _async_create_port_forward(hass, igd_device)

    # sensors
    if data.get(CONF_SENSORS):
        discovery_info = {
            'unit': 'MBytes',
            'udn': data['udn'],
        }
        hass_config = config_entry.data
        hass.async_create_task(discovery.async_load_platform(
            hass, 'sensor', DOMAIN, discovery_info, hass_config))

    async def unload_entry(event):
        """Unload entry on quit."""
        await async_unload_entry(hass, config_entry)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unload_entry)

    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug('async_unload_entry: title: %s, data: %s', config_entry.title, config_entry.data)
    data = config_entry.data
    udn = data['udn']
    igd_device = _get_device(hass, udn)

    # port forward
    if data.get(CONF_PORT_FORWARD):
        _LOGGER.debug('Removing port forward for: %s', igd_device)
        _async_remove_port_forward(hass, igd_device)

    # sensors
    if data.get(CONF_SENSORS):
        # XXX TODO: remove sensors
        pass

    return True
