"""Android TV Remote services."""

from __future__ import annotations

from androidtvremote2 import ConnectionClosed
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, AndroidTVRemoteConfigEntry

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_TEXT = "text"
SEND_TEXT_SERVICE = "send_text"
SEND_TEXT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_TEXT): cv.string,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register Android TV Remote services."""

    async def async_handle_send_text(call: ServiceCall) -> ServiceResponse:
        """Send text."""
        config_entry: AndroidTVRemoteConfigEntry | None = (
            hass.config_entries.async_get_entry(call.data[CONF_CONFIG_ENTRY_ID])
        )
        if not config_entry:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        api = config_entry.runtime_data
        try:
            api.send_text(call.data[CONF_TEXT])
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_closed"
            ) from exc
        return None

    if not hass.services.has_service(DOMAIN, SEND_TEXT_SERVICE):
        hass.services.async_register(
            DOMAIN,
            SEND_TEXT_SERVICE,
            async_handle_send_text,
            schema=SEND_TEXT_SERVICE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )
