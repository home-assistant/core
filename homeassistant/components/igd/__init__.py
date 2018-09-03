"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/igd/
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

from .const import (
    CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS,
    CONF_UDN, CONF_SSDP_DESCRIPTION
)
from .const import DOMAIN
from .const import LOGGER as _LOGGER
from .config_flow import ensure_domain_data


REQUIREMENTS = ['async-upnp-client==0.12.4']
DEPENDENCIES = ['http']

CONF_LOCAL_IP = 'local_ip'
CONF_PORTS = 'ports'

NOTIFICATION_ID = 'igd_notification'
NOTIFICATION_TITLE = 'UPnP/IGD Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=False): cv.boolean,
        vol.Optional(CONF_ENABLE_SENSORS, default=True): cv.boolean,
        vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
    }),
}, extra=vol.ALLOW_EXTRA)


async def _async_create_igd_device(hass: HomeAssistantType,
                                   ssdp_description: str):
    """Create IGD device."""
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
    if igd_device is not None:
        hass.data[DOMAIN]['devices'][udn] = igd_device
    elif udn in hass.data[DOMAIN]['devices']:
        del hass.data[DOMAIN]['devices'][udn]


def _get_device(hass: HomeAssistantType, udn):
    """Get an igd_device by udn."""
    return hass.data[DOMAIN]['devices'].get(udn)


async def _async_add_port_mapping(hass: HomeAssistantType,
                                  igd_device,
                                  local_ip=None):
    """Create a port mapping."""
    # determine local ip, ensure sane IP
    if local_ip is None:
        local_ip = get_local_ip()

    if local_ip == '127.0.0.1':
        _LOGGER.warning('Could not create port mapping, our IP is 127.0.0.1')
        return
    local_ip = IPv4Address(local_ip)

    # create port mapping
    from async_upnp_client import UpnpError
    port = hass.http.server_port
    _LOGGER.debug('Creating port mapping %s:%s:%s (TCP)', port, local_ip, port)
    try:
        await igd_device.async_add_port_mapping(remote_host=None,
                                                external_port=port,
                                                protocol='TCP',
                                                internal_port=port,
                                                internal_client=local_ip,
                                                enabled=True,
                                                description="Home Assistant",
                                                lease_duration=None)
    except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
        _LOGGER.warning('Could not add port mapping')


async def _async_delete_port_mapping(hass: HomeAssistantType, igd_device):
    """Remove a port mapping."""
    from async_upnp_client import UpnpError
    port = hass.http.server_port
    try:
        await igd_device.async_delete_port_mapping(remote_host=None,
                                                   external_port=port,
                                                   protocol='TCP')
    except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
        _LOGGER.warning('Could not delete port mapping')


# config
async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Register a port mapping for Home Assistant via UPnP."""
    ensure_domain_data(hass)

    # ensure sane config
    if DOMAIN not in config:
        return True

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
    ensure_domain_data(hass)
    data = config_entry.data

    # build IGD device
    ssdp_description = data[CONF_SSDP_DESCRIPTION]
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
            'udn': data[CONF_UDN],
        }
        hass_config = config_entry.data
        hass.async_create_task(discovery.async_load_platform(
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
    udn = data[CONF_UDN]

    igd_device = _get_device(hass, udn)
    if igd_device is None:
        return True

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        await _async_delete_port_mapping(hass, igd_device)

    # sensors
    for sensor in hass.data[DOMAIN]['sensors'].get(udn, []):
        await sensor.async_remove()

    # clear stored device
    _store_device(hass, udn, None)

    return True
