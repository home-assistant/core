"""The NZBGet integration."""

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_SPEED,
    DATA_COORDINATOR,
    DEFAULT_SPEED_LIMIT,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)
from .coordinator import NZBGetDataUpdateCoordinator

SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.positive_int}
)


def _get_coordinator(call: ServiceCall) -> NZBGetDataUpdateCoordinator:
    """Service call to pause downloads in NZBGet."""
    entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
        )
    return call.hass.data[DOMAIN][entries[0].entry_id][DATA_COORDINATOR]


def pause(call: ServiceCall) -> None:
    """Service call to pause downloads in NZBGet."""
    _get_coordinator(call).nzbget.pausedownload()


def resume(call: ServiceCall) -> None:
    """Service call to resume downloads in NZBGet."""
    _get_coordinator(call).nzbget.resumedownload()


def set_speed(call: ServiceCall) -> None:
    """Service call to rate limit speeds in NZBGet."""
    _get_coordinator(call).nzbget.rate(call.data[ATTR_SPEED])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-level services."""

    hass.services.async_register(DOMAIN, SERVICE_PAUSE, pause, schema=vol.Schema({}))
    hass.services.async_register(DOMAIN, SERVICE_RESUME, resume, schema=vol.Schema({}))
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SPEED, set_speed, schema=SPEED_LIMIT_SCHEMA
    )
