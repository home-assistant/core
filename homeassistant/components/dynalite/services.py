"""Support for the Dynalite networks."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .bridge import DynaliteBridge
from .const import DOMAIN, LOGGER


class DynaliteService(StrEnum):
    """Store keys for Dynalite services."""

    REQUEST_AREA_PRESET = "request_area_preset"
    REQUEST_CHANNEL_LEVEL = "request_channel_level"


class DynaliteServiceArgument(StrEnum):
    """Store keys for Dynalite service arguments."""

    HOST = "host"
    AREA = "area"
    CHANNEL = "channel"


@callback
def _get_bridges(service_call: ServiceCall) -> list[DynaliteBridge]:
    host = service_call.data.get(DynaliteServiceArgument.HOST, "")
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
            data[DynaliteServiceArgument.AREA],
            data.get(DynaliteServiceArgument.CHANNEL),
        )


async def _request_channel_level(service_call: ServiceCall) -> None:
    bridges = _get_bridges(service_call)
    data = service_call.data
    for bridge in bridges:
        bridge.dynalite_devices.request_channel_level(
            data[DynaliteServiceArgument.AREA], data[DynaliteServiceArgument.CHANNEL]
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Dynalite platform."""
    hass.services.async_register(
        DOMAIN,
        DynaliteService.REQUEST_AREA_PRESET,
        _request_area_preset,
        probatio.Schema(
            {
                probatio.Optional(DynaliteServiceArgument.HOST): cv.string,
                probatio.Required(DynaliteServiceArgument.AREA): int,
                probatio.Optional(DynaliteServiceArgument.CHANNEL): int,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        DynaliteService.REQUEST_CHANNEL_LEVEL,
        _request_channel_level,
        probatio.Schema(
            {
                probatio.Optional(DynaliteServiceArgument.HOST): cv.string,
                probatio.Required(DynaliteServiceArgument.AREA): int,
                probatio.Required(DynaliteServiceArgument.CHANNEL): int,
            }
        ),
    )
