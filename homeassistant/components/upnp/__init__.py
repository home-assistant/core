"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
import asyncio
from ipaddress import ip_address

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import dispatcher
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.discovery import DOMAIN as DISCOVERY_DOMAIN

from .const import (
    CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS,
    CONF_HASS, CONF_LOCAL_IP, CONF_PORTS,
    CONF_UDN, CONF_SSDP_DESCRIPTION,
    SIGNAL_REMOVE_SENSOR,
)
from .const import DOMAIN
from .const import LOGGER as _LOGGER
from .config_flow import ensure_domain_data
from .device import Device


REQUIREMENTS = ['async-upnp-client==0.12.7']
DEPENDENCIES = ['http']

NOTIFICATION_ID = 'upnp_notification'
NOTIFICATION_TITLE = 'UPnP/IGD Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=False): cv.boolean,
        vol.Optional(CONF_ENABLE_SENSORS, default=True): cv.boolean,
        vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
        vol.Optional(CONF_PORTS):
            vol.Schema({
                vol.Any(CONF_HASS, cv.port):
                    vol.Any(CONF_HASS, cv.port)
            })
    }),
}, extra=vol.ALLOW_EXTRA)


def _substitute_hass_ports(ports, hass_port):
    """Substitute 'hass' for the hass_port."""
    ports = ports.copy()

    # substitute 'hass' for hass_port, both keys and values
    if CONF_HASS in ports:
        ports[hass_port] = ports[CONF_HASS]
        del ports[CONF_HASS]

    for port in ports:
        if ports[port] == CONF_HASS:
            ports[port] = hass_port

    return ports


# config
async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Register a port mapping for Home Assistant via UPnP."""
    ensure_domain_data(hass)

    # ensure sane config
    if DOMAIN not in config:
        return True

    if DISCOVERY_DOMAIN not in config:
        _LOGGER.warning('UPNP needs discovery, please enable it')
        return False

    # overridden local ip
    upnp_config = config[DOMAIN]
    if CONF_LOCAL_IP in upnp_config:
        hass.data[DOMAIN]['local_ip'] = upnp_config[CONF_LOCAL_IP]

    # determine ports
    ports = {CONF_HASS: CONF_HASS}  # default, port_mapping disabled by default
    if CONF_PORTS in upnp_config:
        # copy from config
        ports = upnp_config[CONF_PORTS]

    hass.data[DOMAIN]['auto_config'] = {
        'active': True,
        'enable_sensors': upnp_config[CONF_ENABLE_SENSORS],
        'enable_port_mapping': upnp_config[CONF_ENABLE_PORT_MAPPING],
        'ports': ports,
    }

    return True


# config flow
async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry):
    """Set up UPnP/IGD-device from a config entry."""
    ensure_domain_data(hass)
    data = config_entry.data

    # build UPnP/IGD device
    ssdp_description = data[CONF_SSDP_DESCRIPTION]
    try:
        device = await Device.async_create_device(hass, ssdp_description)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error('Unable to create upnp-device')
        return False

    hass.data[DOMAIN]['devices'][device.udn] = device

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        local_ip = hass.data[DOMAIN].get('local_ip')
        ports = hass.data[DOMAIN]['auto_config']['ports']
        _LOGGER.debug('Enabling port mappings: %s', ports)

        hass_port = hass.http.server_port
        ports = _substitute_hass_ports(ports, hass_port)
        await device.async_add_port_mappings(ports, local_ip=local_ip)

    # sensors
    if data.get(CONF_ENABLE_SENSORS):
        _LOGGER.debug('Enabling sensors')

        # register sensor setup handlers
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            config_entry, 'sensor'))

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

    if udn not in hass.data[DOMAIN]['devices']:
        return True
    device = hass.data[DOMAIN]['devices'][udn]

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        _LOGGER.debug('Deleting port mappings')
        await device.async_delete_port_mappings()

    # sensors
    if data.get(CONF_ENABLE_SENSORS):
        _LOGGER.debug('Deleting sensors')
        dispatcher.async_dispatcher_send(hass, SIGNAL_REMOVE_SENSOR, device)

    # clear stored device
    del hass.data[DOMAIN]['devices'][udn]

    return True
