"""Support for exposing Home Assistant via Zeroconf."""
import logging
import socket

import voluptuous as vol

from homeassistant import util
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'zeroconf'


ZEROCONF_TYPE = '_home-assistant._tcp.local.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    from aiozeroconf import Zeroconf, ServiceInfo

    zeroconf = Zeroconf(hass.loop)

    zeroconf_name = '{}.{}'.format(hass.config.location_name, ZEROCONF_TYPE)

    params = {
        'version': __version__,
        'base_url': hass.config.api.base_url,
        # always needs authentication
        'requires_api_password': True,
    }

    host_ip = util.get_local_ip()

    try:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
        info = ServiceInfo(ZEROCONF_TYPE, zeroconf_name, address=host_ip_pton,
                           port=hass.http.server_port, weight=0, priority=0,
                           properties=params)
    except socket.error:
        host_ip_pton = socket.inet_pton(socket.AF_INET6, host_ip)
        info = ServiceInfo(ZEROCONF_TYPE, zeroconf_name, address6=host_ip_pton,
                           port=hass.http.server_port, weight=0, priority=0,
                           properties=params)

    await zeroconf.register_service(info)

    async def stop_zeroconf(event):
        """Stop Zeroconf."""
        await zeroconf.unregister_service(info)
        await zeroconf.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True
