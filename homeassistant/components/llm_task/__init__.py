"""Integration to offer LLM tasks to Home Assistant.

LLM tasks provide a way to use conversation agents for general purpose tasks
outside of an assistant pipeline (e.g. use for summarization in the frontend). This
exposes a conversation agent LLM for general use, without user prompts or customizations.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COMPONENT, DOMAIN
from .entity import LLMTaskEntity
from .http import async_setup as async_setup_conversation_http
from .task import LLMTask, LLMTaskResult, LLMTaskType, async_run_task

__all__ = [
    "DOMAIN",
    "LLMTask",
    "LLMTaskEntity",
    "LLMTaskResult",
    "LLMTaskType",
    "async_run_task",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[LLMTaskEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component
    async_setup_conversation_http(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
