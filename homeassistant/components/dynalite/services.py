"""Support for the Dynalite networks."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .bridge import DynaliteBridge
from .const import (
    ATTR_AREA,
    ATTR_CHANNEL,
    ATTR_HOST,
    DOMAIN,
    LOGGER,
    SERVICE_REQUEST_AREA_PRESET,
    SERVICE_REQUEST_CHANNEL_LEVEL,
)


@callback
def _get_bridges(service_call: ServiceCall) -> list[DynaliteBridge]:
    host = service_call.data.get(ATTR_HOST, "")
    bridges = [
        entry.runtime_data
        for entry in service_call.hass.config_entries.async_loaded_entries(DOMAIN)
        if not host or entry.runtime_data.host == host
    ]
    LOGGER.debug("Selected bridges for service call: %s", bridges)
    return bridges


async def _request_area_preset(service_call: ServiceCall) -> None:
    bridges = _get_bridges(service_call)
    data = service_call.data
    for bridge in bridges:
        bridge.dynalite_devices.request_area_preset(
            data[ATTR_AREA], data.get(ATTR_CHANNEL)
        )


async def _request_channel_level(service_call: ServiceCall) -> None:
    bridges = _get_bridges(service_call)
    data = service_call.data
    for bridge in bridges:
        bridge.dynalite_devices.request_channel_level(
            data[ATTR_AREA], data[ATTR_CHANNEL]
        )


@callback
def setup_services(hass: HomeAssistant) -> None:
    """Set up the Dynalite platform."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_AREA_PRESET,
        _request_area_preset,
        vol.Schema(
            {
                vol.Optional(ATTR_HOST): cv.string,
                vol.Required(ATTR_AREA): int,
                vol.Optional(ATTR_CHANNEL): int,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_CHANNEL_LEVEL,
        _request_channel_level,
        vol.Schema(
            {
                vol.Optional(ATTR_HOST): cv.string,
                vol.Required(ATTR_AREA): int,
                vol.Required(ATTR_CHANNEL): int,
            }
        ),
    )
