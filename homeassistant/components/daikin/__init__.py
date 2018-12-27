"""
Platform for the Daikin AC.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/daikin/
"""
import asyncio
from datetime import timedelta
import logging
from socket import timeout

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOSTS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from . import config_flow  # noqa  pylint_disable=unused-import
from .const import KEY_HOST

REQUIREMENTS = ['pydaikin==0.9']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'daikin'


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

COMPONENT_TYPES = ['climate', 'sensor']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(
            CONF_HOSTS, default=[]
        ): vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Establish connection with Daikin."""
    if DOMAIN not in config:
        return True

    hosts = config[DOMAIN].get(CONF_HOSTS)
    if not hosts:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config.SOURCE_IMPORT}))
    for host in hosts:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': config.SOURCE_IMPORT},
                data={
                    KEY_HOST: host,
                }))
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Establish connection with Daikin."""
    conf = entry.data
    daikin_api = await daikin_api_setup(hass, conf[KEY_HOST])
    if not daikin_api:
        return False
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: daikin_api})
    await asyncio.wait([
        hass.config_entries.async_forward_entry_setup(entry, component)
        for component in COMPONENT_TYPES
    ])
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await asyncio.wait([
        hass.config_entries.async_forward_entry_unload(config_entry, component)
        for component in COMPONENT_TYPES
    ])
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


async def daikin_api_setup(hass, host):
    """Create a Daikin instance only once."""
    from pydaikin.appliance import Appliance
    try:
        with async_timeout.timeout(10):
            device = await hass.async_add_executor_job(Appliance, host)
    except asyncio.TimeoutError:
        _LOGGER.error("Connection to Daikin could not be established")
        return None
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error creating device")
        return None

    name = device.values['name']
    api = DaikinApi(device, name)

    return api


class DaikinApi:
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device, name):
        """Initialize the Daikin Handle."""
        self.device = device
        self.name = name
        self.ip_address = device.ip

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Pull the latest data from Daikin."""
        try:
            self.device.update_status()
        except timeout:
            _LOGGER.warning(
                "Connection failed for %s", self.ip_address
            )

    @property
    def mac(self):
        """Return mac-address of device."""
        return self.device.values.get(CONNECTION_NETWORK_MAC)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        info = self.device.values
        return {
            'connections': {(CONNECTION_NETWORK_MAC, self.mac)},
            'identifieres': self.mac,
            'manufacturer': 'Daikin',
            'model': info.get('model'),
            'name': info.get('name'),
            'sw_version': info.get('ver').replace('_', '.'),
        }
