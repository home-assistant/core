"""Services for the Ness Alarm integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import ATTR_CODE, ATTR_STATE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_OUTPUT_ID, DOMAIN, SERVICE_AUX, SERVICE_PANIC

SERVICE_SCHEMA_PANIC = vol.Schema({vol.Required(ATTR_CODE): cv.string})
SERVICE_SCHEMA_AUX = vol.Schema(
    {
        vol.Required(ATTR_OUTPUT_ID): cv.positive_int,
        vol.Optional(ATTR_STATE, default=True): cv.boolean,
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Ness Alarm services."""

    async def handle_panic(call: ServiceCall) -> None:
        """Handle panic service call."""
        entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )
        client = entries[0].runtime_data
        await client.panic(call.data[ATTR_CODE])

    async def handle_aux(call: ServiceCall) -> None:
        """Handle aux service call."""
        entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )
        client = entries[0].runtime_data
        await client.aux(call.data[ATTR_OUTPUT_ID], call.data[ATTR_STATE])

    hass.services.async_register(
        DOMAIN, SERVICE_PANIC, handle_panic, schema=SERVICE_SCHEMA_PANIC
    )
    hass.services.async_register(
        DOMAIN, SERVICE_AUX, handle_aux, schema=SERVICE_SCHEMA_AUX
    )
