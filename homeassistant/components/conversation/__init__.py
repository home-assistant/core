"""Support for functionality to have conversations with Home Assistant."""

from __future__ import annotations

import logging
import re
from typing import Literal

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .agent_manager import (
    AgentInfo,
    agent_id_validator,
    async_converse,
    async_get_agent,
    get_agent_manager,
)
from .const import (
    ATTR_AGENT_ID,
    ATTR_CONVERSATION_ID,
    ATTR_LANGUAGE,
    ATTR_TEXT,
    DOMAIN,
    HOME_ASSISTANT_AGENT,
    OLD_HOME_ASSISTANT_AGENT,
    SERVICE_PROCESS,
    SERVICE_RELOAD,
)
from .default_agent import async_get_default_agent, async_setup_default_agent
from .entity import ConversationEntity
from .http import async_setup as async_setup_conversation_http
from .models import AbstractConversationAgent, ConversationInput, ConversationResult

__all__ = [
    "DOMAIN",
    "HOME_ASSISTANT_AGENT",
    "OLD_HOME_ASSISTANT_AGENT",
    "async_converse",
    "async_get_agent_info",
    "async_set_agent",
    "async_setup",
    "async_unset_agent",
    "ConversationEntity",
    "ConversationInput",
    "ConversationResult",
]

_LOGGER = logging.getLogger(__name__)

REGEX_TYPE = type(re.compile(""))

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

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): vol.Schema(
            {
                vol.Optional("intents"): vol.Schema(
                    {cv.string: vol.All(cv.ensure_list, [cv.string])}
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
@bind_hass
def async_set_agent(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    agent: AbstractConversationAgent,
) -> None:
    """Set the agent to handle the conversations."""
    get_agent_manager(hass).async_set_agent(config_entry.entry_id, agent)


@callback
@bind_hass
def async_unset_agent(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Set the agent to handle the conversations."""
    get_agent_manager(hass).async_unset_agent(config_entry.entry_id)


async def async_get_conversation_languages(
    hass: HomeAssistant, agent_id: str | None = None
) -> set[str] | Literal["*"]:
    """Return languages supported by conversation agents.

    If an agent is specified, returns a set of languages supported by that agent.
    If no agent is specified, return a set with the union of languages supported by
    all conversation agents.
    """
    agent_manager = get_agent_manager(hass)
    entity_component: EntityComponent[ConversationEntity] = hass.data[DOMAIN]
    languages: set[str] = set()
    agents: list[ConversationEntity | AbstractConversationAgent]

    if agent_id:
        agent = async_get_agent(hass, agent_id)

        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        agents = [agent]

    else:
        agents = list(entity_component.entities)
        for info in agent_manager.async_get_agent_info():
            agent = agent_manager.async_get_agent(info.id)
            assert agent is not None
            agents.append(agent)

    for agent in agents:
        if agent.supported_languages == MATCH_ALL:
            return MATCH_ALL
        for language_tag in agent.supported_languages:
            languages.add(language_tag)

    return languages


@callback
def async_get_agent_info(
    hass: HomeAssistant,
    agent_id: str | None = None,
) -> AgentInfo | None:
    """Get information on the agent or None if not found."""
    agent = async_get_agent(hass, agent_id)

    if agent is None:
        return None

    if isinstance(agent, ConversationEntity):
        name = agent.name
        if not isinstance(name, str):
            name = agent.entity_id
        return AgentInfo(id=agent.entity_id, name=name)

    manager = get_agent_manager(hass)

    for agent_info in manager.async_get_agent_info():
        if agent_info.id == agent_id:
            return agent_info

    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component: EntityComponent[ConversationEntity] = EntityComponent(
        _LOGGER, DOMAIN, hass
    )
    hass.data[DOMAIN] = entity_component

    await async_setup_default_agent(
        hass, entity_component, config.get(DOMAIN, {}).get("intents", {})
    )

    # Temporary migration. We can remove this in 2024.10
    from homeassistant.components.assist_pipeline import (  # pylint: disable=import-outside-toplevel
        async_migrate_engine,
    )

    async_migrate_engine(
        hass, "conversation", OLD_HOME_ASSISTANT_AGENT, HOME_ASSISTANT_AGENT
    )

    async def handle_process(service: ServiceCall) -> ServiceResponse:
        """Parse text into commands."""
        text = service.data[ATTR_TEXT]
        _LOGGER.debug("Processing: <%s>", text)
        try:
            result = await async_converse(
                hass=hass,
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

    async def handle_reload(service: ServiceCall) -> None:
        """Reload intents."""
        agent = async_get_default_agent(hass)
        await agent.async_reload(language=service.data.get(ATTR_LANGUAGE))

    hass.services.async_register(
        DOMAIN,
        SERVICE_PROCESS,
        handle_process,
        schema=SERVICE_PROCESS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, handle_reload, schema=SERVICE_RELOAD_SCHEMA
    )
    async_setup_conversation_http(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[ConversationEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[ConversationEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)
