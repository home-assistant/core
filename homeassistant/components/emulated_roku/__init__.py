"""Support for Roku API emulation."""
import voluptuous as vol

from homeassistant import config_entries, util
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .binding import EmulatedRoku
from .config_flow import configured_servers
from .const import (
    CONF_ADVERTISE_IP, CONF_ADVERTISE_PORT, CONF_HOST_IP, CONF_LISTEN_PORT,
    CONF_SERVERS, CONF_UPNP_BIND_MULTICAST, DOMAIN)

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

    existing_servers = configured_servers(hass)

    for entry in conf[CONF_SERVERS]:
        if entry[CONF_NAME] not in existing_servers:
            hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': config_entries.SOURCE_IMPORT},
                data=entry
            ))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up an emulated roku server from a config entry."""
    config = config_entry.data

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

    hass.data[DOMAIN][name] = server

    return await server.setup()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    name = entry.data[CONF_NAME]
    server = hass.data[DOMAIN].pop(name)
    return await server.unload()
