"""Services for the conversation integration."""

import logging

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.reload import async_integration_yaml_config

from .agent_manager import agent_id_validator, async_converse, get_agent_manager
from .const import DOMAIN, ConversationService, ConversationServiceArgument
from .util import get_config_intents

_LOGGER = logging.getLogger(__name__)

SERVICE_PROCESS_SCHEMA = probatio.Schema(
    {
        probatio.Required(ConversationServiceArgument.TEXT): cv.string,
        probatio.Optional(ConversationServiceArgument.LANGUAGE): cv.string,
        probatio.Optional(ConversationServiceArgument.AGENT_ID): agent_id_validator,
        probatio.Optional(ConversationServiceArgument.CONVERSATION_ID): cv.string,
    }
)


SERVICE_RELOAD_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ConversationServiceArgument.LANGUAGE): cv.string,
        probatio.Optional(ConversationServiceArgument.AGENT_ID): agent_id_validator,
    }
)


async def _async_handle_process(service: ServiceCall) -> ServiceResponse:
    """Parse text into commands."""
    text = service.data[ConversationServiceArgument.TEXT]
    _LOGGER.debug("Processing: <%s>", text)
    try:
        result = await async_converse(
            hass=service.hass,
            text=text,
            conversation_id=service.data.get(
                ConversationServiceArgument.CONVERSATION_ID
            ),
            context=service.context,
            language=service.data.get(ConversationServiceArgument.LANGUAGE),
            agent_id=service.data.get(ConversationServiceArgument.AGENT_ID),
        )
    except intent.IntentHandleError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="process_failed",
            translation_placeholders={"text": text, "error": str(err)},
        ) from err

    if service.return_response:
        return result.as_dict()

    return None


async def _async_handle_reload(service: ServiceCall) -> None:
    """Reload intents."""
    hass = service.hass
    manager = get_agent_manager(hass)
    language = service.data.get(ConversationServiceArgument.LANGUAGE)
    if language is None:
        conf = await async_integration_yaml_config(hass, DOMAIN)
        if conf is not None:
            config_intents = get_config_intents(conf, hass.config.path())
            manager.update_config_intents(config_intents)

    agent = manager.default_agent
    if agent is not None:
        await agent.async_reload(language=language)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the conversation services."""
    hass.services.async_register(
        DOMAIN,
        ConversationService.PROCESS,
        _async_handle_process,
        schema=SERVICE_PROCESS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        ConversationService.RELOAD,
        _async_handle_reload,
        schema=SERVICE_RELOAD_SCHEMA,
    )
