"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""


import asyncio
from ipaddress import IPv4Address
from ipaddress import ip_address

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import get_local_ip
from homeassistant.components.discovery import DOMAIN as DISCOVERY_DOMAIN

from .const import CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS
from .const import DOMAIN
from .const import LOGGER as _LOGGER
import homeassistant.components.igd.config_flow  # register the handler


REQUIREMENTS = ['async-upnp-client==0.12.4']
DEPENDENCIES = ['http']  # ,'discovery']

CONF_LOCAL_IP = 'local_ip'
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
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=False): cv.boolean,
        vol.Optional(CONF_ENABLE_SENSORS, default=True): cv.boolean,
        vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
        vol.Optional(CONF_UNITS, default="MBytes"): vol.In(UNITS),
    }),
}, extra=vol.ALLOW_EXTRA)


async def _async_create_igd_device(hass: HomeAssistantType,
                                   ssdp_description: str):
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


async def _async_add_port_mapping(hass: HomeAssistantType,
                                  igd_device,
                                  local_ip=None):
    """Create a port mapping."""
    # determine local ip, ensure sane IP
    if local_ip is None:
        local_ip = get_local_ip()

    if local_ip == '127.0.0.1':
        _LOGGER.warning('Could not create port mapping, our IP is 127.0.0.1')
        return False
    local_ip = IPv4Address(local_ip)

    # create port mapping
    port = hass.http.server_port
    _LOGGER.debug('Creating port mapping %s:%s:%s (TCP)', port, local_ip, port)
    await igd_device.async_add_port_mapping(remote_host=None,
                                            external_port=port,
                                            protocol='TCP',
                                            internal_port=port,
                                            internal_client=local_ip,
                                            enabled=True,
                                            description="Home Assistant",
                                            lease_duration=None)

    return True


async def _async_delete_port_mapping(hass: HomeAssistantType, igd_device):
    """Remove a port mapping."""
    port = hass.http.server_port
    await igd_device.async_delete_port_mapping(remote_host=None,
                                               external_port=port,
                                               protocol='TCP')


# config
async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Register a port mapping for Home Assistant via UPnP."""
    # defaults
    hass.data[DOMAIN] = {
        'auto_config': {
            'active': False,
            'port_forward': False,
            'sensors': False,
        }
    }

    # ensure sane config
    if DOMAIN not in config:
        return False

    if DISCOVERY_DOMAIN not in config:
        _LOGGER.warning('IGD needs discovery, please enable it')
        return False

    igd_config = config[DOMAIN]
    if CONF_LOCAL_IP in igd_config:
        hass.data[DOMAIN]['local_ip'] = igd_config[CONF_LOCAL_IP]

    hass.data[DOMAIN]['auto_config'] = {
        'active': True,
        'port_forward': igd_config[CONF_ENABLE_PORT_MAPPING],
        'sensors': igd_config[CONF_ENABLE_SENSORS],
    }
    _LOGGER.debug('Enabled auto_config: %s', hass.data[DOMAIN]['auto_config'])

    return True


# config flow
async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry):
    """Set up a bridge from a config entry."""
    data = config_entry.data
    ssdp_description = data['ssdp_description']

    # build IGD device
    try:
        igd_device = await _async_create_igd_device(hass, ssdp_description)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    _store_device(hass, igd_device.udn, igd_device)

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        local_ip = hass.data[DOMAIN].get('local_ip')
        await _async_add_port_mapping(hass, igd_device, local_ip=local_ip)

    # sensors
    if data.get(CONF_ENABLE_SENSORS):
        discovery_info = {
            'unit': 'MBytes',
            'udn': data['udn'],
        }
        hass_config = config_entry.data
        hass.async_create_task(
            discovery.async_load_platform(
                hass, 'sensor', DOMAIN, discovery_info, hass_config))

    async def unload_entry(event):
        """Unload entry on quit."""
        await async_unload_entry(hass, config_entry)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unload_entry)

    return True


async def async_unload_entry(hass: HomeAssistantType,
                             config_entry: ConfigEntry):
    """Unload a config entry."""
    data = config_entry.data
    udn = data['udn']

    igd_device = _get_device(hass, udn)
    if igd_device is None:
        return True

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        await _async_delete_port_mapping(hass, igd_device)

    # sensors
    if data.get(CONF_ENABLE_SENSORS):
        # XXX TODO: remove sensors
        pass

    _store_device(hass, udn, None)

    return True
