"""
Will open a port in your router for Home Assistant and provide statistics.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/igd/
"""

import asyncio
from ipaddress import ip_address

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.discovery import DOMAIN as DISCOVERY_DOMAIN

from .const import (
    CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS,
    CONF_HASS, CONF_LOCAL_IP, CONF_PORTS,
    CONF_UDN, CONF_SSDP_DESCRIPTION,
)
from .const import DOMAIN
from .const import LOGGER as _LOGGER
from .config_flow import ensure_domain_data
from .device import Device


REQUIREMENTS = ['async-upnp-client==0.12.4']
DEPENDENCIES = ['http']

NOTIFICATION_ID = 'igd_notification'
NOTIFICATION_TITLE = 'UPnP/IGD Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ENABLE_PORT_MAPPING, default=False): cv.boolean,
        vol.Optional(CONF_ENABLE_SENSORS, default=True): cv.boolean,
        vol.Optional(CONF_LOCAL_IP): vol.All(ip_address, cv.string),
        vol.Optional(CONF_PORTS):
            vol.Schema({vol.Any(CONF_HASS, cv.positive_int): cv.positive_int})
    }),
}, extra=vol.ALLOW_EXTRA)


# config
async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Register a port mapping for Home Assistant via UPnP."""
    _LOGGER.debug('async_setup: %s', config.get(DOMAIN))
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

    # determine ports
    ports = {}
    if CONF_PORTS in igd_config:
        ports = igd_config[CONF_PORTS]

        if CONF_HASS in ports:
            internal_port = hass.http.server_port
            ports[internal_port] = ports[CONF_HASS]
            del ports[CONF_HASS]

    hass.data[DOMAIN]['auto_config'] = {
        'active': True,
        'port_forward': igd_config[CONF_ENABLE_PORT_MAPPING],
        'ports': ports,
        'sensors': igd_config[CONF_ENABLE_SENSORS],
    }

    return True


# config flow
async def async_setup_entry(hass: HomeAssistantType,
                            config_entry: ConfigEntry):
    """Set up a bridge from a config entry."""
    _LOGGER.debug('async_setup_entry: %s', config_entry.data)
    ensure_domain_data(hass)
    data = config_entry.data

    # build IGD device
    ssdp_description = data[CONF_SSDP_DESCRIPTION]
    try:
        device = await Device.async_create_device(hass, ssdp_description)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    hass.data[DOMAIN]['devices'][device.udn] = device

    # port mapping
    if data.get(CONF_ENABLE_PORT_MAPPING):
        local_ip = hass.data[DOMAIN].get('local_ip')
        ports = hass.data[DOMAIN]['auto_config']['ports']
        _LOGGER.debug('Enabling port mappings: %s', ports)
        await device.async_add_port_mappings(ports, local_ip=local_ip)

    # sensors
    if data.get(CONF_ENABLE_SENSORS):
        _LOGGER.debug('Enabling sensors')
        discovery_info = {
            'udn': device.udn,
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
    _LOGGER.debug('async_unload_entry: %s', config_entry.data)
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
    for sensor in hass.data[DOMAIN]['sensors'].get(udn, []):
        _LOGGER.debug('Deleting sensor: %s', sensor)
        await sensor.async_remove()

    # clear stored device
    del hass.data[DOMAIN]['devices'][udn]

    return True
