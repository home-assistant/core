"""Support for the Dynalite networks."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_AREA,
    ATTR_CHANNEL,
    ATTR_HOST,
    DOMAIN,
    LOGGER,
    SERVICE_REQUEST_AREA_PRESET,
    SERVICE_REQUEST_CHANNEL_LEVEL,
)

_SERVICES = [SERVICE_REQUEST_AREA_PRESET, SERVICE_REQUEST_CHANNEL_LEVEL]


async def _run_dynalite_service_call(service_call: ServiceCall) -> None:
    data = service_call.data
    host = data.get(ATTR_HOST, "")
    bridges = [
        bridge
        for bridge in service_call.hass.data[DOMAIN].values()
        if not host or bridge.host == host
    ]
    LOGGER.debug("Selected bridged for service call: %s", bridges)
    if service_call.service == SERVICE_REQUEST_AREA_PRESET:
        bridge_attr = "request_area_preset"
    elif service_call.service == SERVICE_REQUEST_CHANNEL_LEVEL:
        bridge_attr = "request_channel_level"
    for bridge in bridges:
        getattr(bridge.dynalite_devices, bridge_attr)(
            data[ATTR_AREA], data.get(ATTR_CHANNEL)
        )


@callback
def setup_services(hass: HomeAssistant) -> None:
    """Set up the Dynalite platform."""
    for service_name in _SERVICES:
        hass.services.async_register(
            DOMAIN,
            service_name,
            _run_dynalite_service_call,
            vol.Schema(
                {
                    vol.Optional(ATTR_HOST): cv.string,
                    vol.Required(ATTR_AREA): int,
                    vol.Required(ATTR_CHANNEL): int,
                }
            ),
        )
