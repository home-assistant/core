"""
This module will attempt to open a port in your router for Home Assistant.

For more details about UPnP, please refer to the documentation at
https://home-assistant.io/components/upnp/
"""
import logging

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP)

DEPENDENCIES = ["api"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "upnp"


def setup(hass, config):
    """Register a port mapping for Home Assistant via UPnP."""
    # pylint: disable=import-error
    import miniupnpc

    # pylint: disable=no-member
    upnp = miniupnpc.UPnP()

    upnp.discoverdelay = 200
    upnp.discover()
    try:
        upnp.selectigd()
    # pylint: disable=broad-except
    except Exception:
        _LOGGER.exception("Error when attempting to discover a UPnP IGD")
        return False

    upnp.addportmapping(hass.config.api.port, "TCP",
                        hass.config.api.host, hass.config.api.port,
                        "Home Assistant", "")

    def deregister_port(event):
        """De-register the UPnP port mapping."""
        upnp.deleteportmapping(hass.config.api.port, "TCP")

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, deregister_port)

    return True
