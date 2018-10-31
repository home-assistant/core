"""
This module exposes Home Assistant via Zeroconf.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zeroconf/
"""
import logging
import socket

import voluptuous as vol

from homeassistant import util
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)

REQUIREMENTS = ['zeroconf==0.21.3']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'zeroconf'


ZEROCONF_TYPE = '_home-assistant._tcp.local.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    from zeroconf import Zeroconf, ServiceInfo

    zeroconf = Zeroconf()

    zeroconf_name = '{}.{}'.format(hass.config.location_name, ZEROCONF_TYPE)

    requires_api_password = hass.config.api.api_password is not None
    params = {
        'version': __version__,
        'base_url': hass.config.api.base_url,
        'requires_api_password': requires_api_password,
    }

    host_ip = util.get_local_ip()

    try:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
    except socket.error:
        host_ip_pton = socket.inet_pton(socket.AF_INET6, host_ip)

    info = ServiceInfo(ZEROCONF_TYPE, zeroconf_name, host_ip_pton,
                       hass.http.server_port, 0, 0, params)

    zeroconf.register_service(info)

    def stop_zeroconf(event):
        """Stop Zeroconf."""
        zeroconf.unregister_service(info)
        zeroconf.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True
