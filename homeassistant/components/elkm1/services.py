"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""

from __future__ import annotations

from elkm1_lib.elk import Elk, Panel
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import ELKM1Data

SPEAK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("number"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
        vol.Optional("prefix", default=""): cv.string,
    }
)

SET_TIME_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("prefix", default=""): cv.string,
    }
)


def _find_elk_by_prefix(hass: HomeAssistant, prefix: str) -> Elk | None:
    """Search all config entries for a given prefix."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not entry.runtime_data:
            continue
        elk_data: ELKM1Data = entry.runtime_data
        if elk_data.prefix == prefix:
            return elk_data.elk
    return None


@callback
def _async_get_elk_panel(service: ServiceCall) -> Panel:
    """Get the ElkM1 panel from a service call."""
    prefix = service.data["prefix"]
    elk = _find_elk_by_prefix(service.hass, prefix)
    if elk is None:
        raise HomeAssistantError(f"No ElkM1 with prefix '{prefix}' found")
    return elk.panel


@callback
def _speak_word_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).speak_word(service.data["number"])


@callback
def _speak_phrase_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).speak_phrase(service.data["number"])


@callback
def _set_time_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).set_time(dt_util.now())


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Create ElkM1 services."""

    hass.services.async_register(
        DOMAIN, "speak_word", _speak_word_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "speak_phrase", _speak_phrase_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_time", _set_time_service, SET_TIME_SERVICE_SCHEMA
    )
