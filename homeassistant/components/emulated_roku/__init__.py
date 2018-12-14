"""
Support for Roku API emulation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_roku/
"""
import voluptuous as vol

from homeassistant import config_entries, util
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .binding import EmulatedRoku
from .config_flow import configured_servers
from .const import (
    CONF_ADVERTISE_IP, CONF_ADVERTISE_PORT, CONF_HOST_IP, CONF_LISTEN_PORT,
    CONF_SERVERS, CONF_UPNP_BIND_MULTICAST, DOMAIN)

REQUIREMENTS = ['emulated_roku==0.1.5']

SERVER_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_LISTEN_PORT): cv.port,
    vol.Optional(CONF_HOST_IP): cv.string,
    vol.Optional(CONF_ADVERTISE_IP): cv.string,
    vol.Optional(CONF_ADVERTISE_PORT): cv.port,
    vol.Optional(CONF_UPNP_BIND_MULTICAST): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_SERVERS):
            vol.All(cv.ensure_list, [SERVER_CONFIG_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the emulated roku component."""
    conf = config.get(DOMAIN)

    if conf is None:
        return True

    for entry in conf[CONF_SERVERS]:
        if entry[CONF_NAME] not in configured_servers(hass):
            hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': config_entries.SOURCE_IMPORT},
                data=entry
            ))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up an emulated roku server from a config entry."""
    return await create_emulated_roku(hass, config_entry.data)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    name = entry.data[CONF_NAME]
    server = hass.data[DOMAIN].pop(name)
    return server.stop()


async def create_emulated_roku(hass, config):
    """Set up an emulated roku server from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    name = config[CONF_NAME]
    listen_port = config[CONF_LISTEN_PORT]
    host_ip = config.get(CONF_HOST_IP) or util.get_local_ip()
    advertise_ip = config.get(CONF_ADVERTISE_IP)
    advertise_port = config.get(CONF_ADVERTISE_PORT)
    upnp_bind_multicast = config.get(CONF_UPNP_BIND_MULTICAST)

    server = EmulatedRoku(hass, name, host_ip, listen_port,
                          advertise_ip, advertise_port, upnp_bind_multicast)

    @callback
    def emulated_roku_shutdown(event):
        """Wrap the call to emulated_roku.stop."""
        server.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               emulated_roku_shutdown)

    hass.data[DOMAIN][name] = server

    return await server.async_setup()
