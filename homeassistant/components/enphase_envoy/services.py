"""Implement Enphase Envoy services."""

from __future__ import annotations

import logging

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
SERVICE_GET_RAW_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): str,
    }
)
RAW_SERVICE_LIST: dict[str, str] = {"get_raw_tariff": URL_TARIFF}

_LOGGER = logging.getLogger(__name__)


def _find_envoy_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> EnphaseUpdateCoordinator:
    """Find envoy config entry from service data and return envoy coordinator."""
    identifier = str(call.data.get(ATTR_CONFIG_ENTRY_ID))
    if not (entry := hass.config_entries.async_get_entry(identifier)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="envoy_service_envoy_not_found",
            translation_placeholders={
                "service": call.service,
                "args": identifier,
            },
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_initialized",
            translation_placeholders={"service": call.service},
        )
    coordinator: EnphaseUpdateCoordinator = entry.runtime_data
    return coordinator


async def setup_hass_services(hass: HomeAssistant) -> ServiceResponse:
    """Configure Home Assistant services for Enphase_Envoy."""

    async def get_raw_service(call: ServiceCall) -> ServiceResponse:
        """Return tariff data from envoy.data.raw cache."""
        coordinator = _find_envoy_coordinator(hass, call)
        envoy_to_use = coordinator.envoy
        if not envoy_to_use.data or not envoy_to_use.data.raw:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_initialized",
                translation_placeholders={"service": call.service},
            )
        if not (data := envoy_to_use.data.raw.get(RAW_SERVICE_LIST[call.service])):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_collected",
                translation_placeholders={"service": call.service},
            )
        return {"raw": data}

    # declare services
    for service in RAW_SERVICE_LIST:
        hass.services.async_register(
            DOMAIN,
            service,
            get_raw_service,
            schema=SERVICE_GET_RAW_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )

    return None
