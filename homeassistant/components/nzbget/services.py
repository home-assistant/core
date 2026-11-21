"""The NZBGet integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_SPEED_LIMIT, DOMAIN
from .coordinator import NZBGetDataUpdateCoordinator


class NZBGetService(StrEnum):
    """Store keys for NZBGet services."""

    PAUSE = "pause"
    RESUME = "resume"
    SET_SPEED = "set_speed"


class NZBGetServiceArgument(StrEnum):
    """Store keys for NZBGet service arguments."""

    SPEED = "speed"


SPEED_LIMIT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            NZBGetServiceArgument.SPEED, default=DEFAULT_SPEED_LIMIT
        ): cv.positive_int
    }
)


def _get_coordinator(call: ServiceCall) -> NZBGetDataUpdateCoordinator:
    """Service call to pause downloads in NZBGet."""
    entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
        )
    return entries[0].runtime_data


def pause(call: ServiceCall) -> None:
    """Service call to pause downloads in NZBGet."""
    _get_coordinator(call).nzbget.pausedownload()


def resume(call: ServiceCall) -> None:
    """Service call to resume downloads in NZBGet."""
    _get_coordinator(call).nzbget.resumedownload()


def set_speed(call: ServiceCall) -> None:
    """Service call to rate limit speeds in NZBGet."""
    _get_coordinator(call).nzbget.rate(call.data[NZBGetServiceArgument.SPEED])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-level services."""

    hass.services.async_register(
        DOMAIN, NZBGetService.PAUSE, pause, schema=probatio.Schema({})
    )
    hass.services.async_register(
        DOMAIN, NZBGetService.RESUME, resume, schema=probatio.Schema({})
    )
    hass.services.async_register(
        DOMAIN, NZBGetService.SET_SPEED, set_speed, schema=SPEED_LIMIT_SCHEMA
    )
