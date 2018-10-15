"""Component to embed LIFX."""
import asyncio
import socket

import async_timeout
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN


DOMAIN = 'lifx'
REQUIREMENTS = ['aiolifx==0.6.3']

CONF_SERVER = 'server'
CONF_BROADCAST = 'broadcast'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        LIGHT_DOMAIN: {
            vol.Optional(CONF_SERVER): cv.string,
            vol.Optional(CONF_BROADCAST): cv.string,
        }
    }
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the LIFX component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up LIFX from a config entry."""
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, LIGHT_DOMAIN))
    return True


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    import aiolifx

    manager = DiscoveryManager()
    lifx_discovery = aiolifx.LifxDiscovery(hass.loop, manager)
    coro = hass.loop.create_datagram_endpoint(
        lambda: lifx_discovery,
        family=socket.AF_INET)
    hass.async_create_task(coro)

    has_devices = await manager.found_devices()
    lifx_discovery.cleanup()

    return has_devices


config_entry_flow.register_discovery_flow(
    DOMAIN, 'LIFX', _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL)


class DiscoveryManager:
    """Temporary LIFX manager for discovering any bulb."""

    def __init__(self):
        """Initialize the manager."""
        self._event = asyncio.Event()

    async def found_devices(self):
        """Return whether any device could be discovered."""
        try:
            async with async_timeout.timeout(2):
                await self._event.wait()

                # Let bulbs recover from the discovery
                await asyncio.sleep(1)

                return True
        except asyncio.TimeoutError:
            return False

    def register(self, bulb):
        """Handle aiolifx detected bulb."""
        self._event.set()

    def unregister(self, bulb):
        """Handle aiolifx disappearing bulbs."""
        pass
