"""Support for functionality to have conversations with Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent

from .agent_manager import agent_id_validator, async_converse
from .const import (
    ATTR_AGENT_ID,
    ATTR_CONVERSATION_ID,
    ATTR_LANGUAGE,
    ATTR_TEXT,
    DATA_DEFAULT_ENTITY,
    DOMAIN,
    SERVICE_PROCESS,
    SERVICE_RELOAD,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_PROCESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_AGENT_ID): agent_id_validator,
        vol.Optional(ATTR_CONVERSATION_ID): cv.string,
    }
)


SERVICE_RELOAD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_AGENT_ID): agent_id_validator,
    }
)


async def _handle_process(service: ServiceCall) -> ServiceResponse:
    """Parse text into commands."""
    text = service.data[ATTR_TEXT]
    _LOGGER.debug("Processing: <%s>", text)
    try:
        result = await async_converse(
            hass=service.hass,
            text=text,
            conversation_id=service.data.get(ATTR_CONVERSATION_ID),
            context=service.context,
            language=service.data.get(ATTR_LANGUAGE),
            agent_id=service.data.get(ATTR_AGENT_ID),
        )
    except intent.IntentHandleError as err:
        raise HomeAssistantError(f"Error processing {text}: {err}") from err

    if service.return_response:
        return result.as_dict()

    return None


async def _handle_reload(service: ServiceCall) -> None:
    """Reload intents."""
    await service.hass.data[DATA_DEFAULT_ENTITY].async_reload(
        language=service.data.get(ATTR_LANGUAGE)
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS,
        _handle_process,
        schema=SERVICE_PROCESS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, _handle_reload, schema=SERVICE_RELOAD_SCHEMA
    )
