"""Implement Enphase Envoy services."""

from __future__ import annotations

import logging
from typing import Never

from pyenphase.const import URL_TARIFF
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
RAW_SERVICE_LIST: dict[str, str] = {"get_raw_tariff": URL_TARIFF}

_LOGGER = logging.getLogger(__name__)


def _raise_validation(call: ServiceCall, key: str, param: str = "") -> Never:
    """Raise Servicevalidation error."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders={
            "service": call.service,
            "args": param,
        },
    )


def _find_envoy_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> EnphaseUpdateCoordinator:
    """Find envoy config entry from service data and return envoy coordinator."""
    identifier = str(call.data.get(ATTR_CONFIG_ENTRY_ID))
    if not (entry := hass.config_entries.async_get_entry(identifier)):
        _raise_validation(call, "envoy_service_no_config", identifier)
    if entry.state is not ConfigEntryState.LOADED:
        _raise_validation(call, "not_initialized", identifier)

    coordinator: EnphaseUpdateCoordinator = entry.runtime_data
    if (
        not (coordinator)
        or not (envoy_to_use := coordinator.envoy)
        or not envoy_to_use.data
        or not envoy_to_use.data.raw
    ):
        _raise_validation(call, "not_initialized", identifier)
    return coordinator


async def setup_hass_services(hass: HomeAssistant) -> ServiceResponse:
    """Configure Home Assistant services for Enphase_Envoy."""

    async def get_raw_service(call: ServiceCall) -> ServiceResponse:
        """Return tariff data from envoy.data.raw cache."""
        coordinator = _find_envoy_coordinator(hass, call)
        envoy_to_use = coordinator.envoy
        if not envoy_to_use.data or not (
            data := envoy_to_use.data.raw.get(RAW_SERVICE_LIST[call.service])
        ):
            _raise_validation(call, "not_collected", call.service)
        return {"raw": data}

    # declare services
    for service in RAW_SERVICE_LIST:
        hass.services.async_register(
            DOMAIN,
            service,
            get_raw_service,
            schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str}),
            supports_response=SupportsResponse.OPTIONAL,
        )

    return None
