"""
Support for Roku API emulation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_roku/
"""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import util
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from .config_flow import configured_servers
from .const import (DOMAIN, CONF_SERVERS,
                    CONF_LISTEN_PORT, CONF_HOST_IP,
                    CONF_ADVERTISE_IP, CONF_ADVERTISE_PORT,
                    CONF_UPNP_BIND_MULTICAST)
from .emulated_roku import EmulatedRoku

REQUIREMENTS = ['emulated_roku==0.1.5']

DEFAULT_UPNP_BIND_MULTICAST = True

SERVER_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_LISTEN_PORT): cv.port,
    vol.Optional(CONF_HOST_IP): cv.string,
    vol.Optional(CONF_ADVERTISE_IP): cv.string,
    vol.Optional(CONF_ADVERTISE_PORT): cv.port,
    vol.Optional(CONF_UPNP_BIND_MULTICAST,
                 default=DEFAULT_UPNP_BIND_MULTICAST): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_SERVERS):
            vol.All(cv.ensure_list, [SERVER_CONFIG_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def create_emulated_roku(hass, config):
    """Set up an emulated roku server from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    name = config.get(CONF_NAME)
    listen_port = config.get(CONF_LISTEN_PORT)
    host_ip = config.get(CONF_HOST_IP) or util.get_local_ip()
    advertise_ip = config.get(CONF_ADVERTISE_IP)
    advertise_port = config.get(CONF_ADVERTISE_PORT)
    upnp_bind_multicast = config.get(CONF_UPNP_BIND_MULTICAST,
                                     DEFAULT_UPNP_BIND_MULTICAST)

    server = EmulatedRoku(hass, name, host_ip, listen_port,
                          advertise_ip, advertise_port, upnp_bind_multicast)

    @callback
    def emulated_roku_shutdown(event):
        """Wrap the call to emulated_roku.stop."""
        server.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               emulated_roku_shutdown)

    hass.data[DOMAIN][util.slugify(name)] = server

    return await server.async_setup()


async def async_setup(hass, config):
    """Set up the emulated roku component."""
    conf = config.get(DOMAIN)

    server_entries = configured_servers(hass)

    if CONF_SERVERS in conf:
        for entry in conf[CONF_SERVERS]:
            name = util.slugify(entry[CONF_NAME])
            if name not in server_entries:
                await create_emulated_roku(hass, entry)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up an emulated roku server from a config entry."""
    return await create_emulated_roku(hass, config_entry.data)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    name = util.slugify(entry.data[CONF_NAME])
    server = hass.data[DOMAIN].pop(name)
    return server.stop()
