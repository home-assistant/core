"""
Support for Roku API emulation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_roku/
"""

from homeassistant import util
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from .const import (DOMAIN, CONF_LISTEN_PORT, CONF_HOST_IP,
                    CONF_ADVERTISE_IP, CONF_ADVERTISE_PORT,
                    CONF_UPNP_BIND_MULTICAST,
                    DEFAULT_UPNP_BIND_MULTICAST)

from .binding import EmulatedRoku

from . import config_flow  # noqa  # pylint: disable=unused-import

REQUIREMENTS = ['emulated_roku==0.1.5']


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up an emulated roku server from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    config = config_entry.data

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


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    name = util.slugify(entry.data[CONF_NAME])
    server = hass.data[DOMAIN].pop(name)
    return server.stop()
