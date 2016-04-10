"""
This module exposes Home Assistant via Zeroconf, also sometimes known as
Bonjour, Rendezvous, Avahi or Multicast DNS (mDNS).

For more details about Zeroconf, please refer to the documentation at
https://home-assistant.io/components/zeroconf/
"""
import logging
import socket

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, __version__)

import homeassistant.util as util

REQUIREMENTS = ["zeroconf==0.17.5"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zeroconf"

ZEROCONF_TYPE = "_home-assistant._tcp.local."

DEPENDENCIES = ["http", "api"]

def setup(hass, config):

  from zeroconf import Zeroconf, ServiceInfo

  zeroconf = Zeroconf()

  zeroconf_name = "{}.{}".format(hass.config.location_name,
                                 ZEROCONF_TYPE)

  params = {"version": __version__, "base_url": hass.http.base_url,
            "has_password": (hass.http.api_password != "")}

  info = ServiceInfo(ZEROCONF_TYPE, zeroconf_name,
                     socket.inet_aton(util.get_local_ip()),
                     hass.http.server_address[1], 0, 0, params)

  zeroconf.register_service(info)

  def stop_zeroconf(event):
      """Stop Zeroconf."""
      zeroconf.unregister_all_services()

  hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

  return True
