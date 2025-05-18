"""Integration to offer AI tasks to Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COMPONENT, DOMAIN
from .entity import AITaskEntity
from .http import async_setup as async_setup_conversation_http
from .task import GenTextTask, GenTextTaskResult, GenTextTaskType, async_generate_text

__all__ = [
    "DOMAIN",
    "AITaskEntity",
    "GenTextTask",
    "GenTextTaskResult",
    "GenTextTaskType",
    "async_generate_text",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the process service."""
    entity_component = EntityComponent[AITaskEntity](_LOGGER, DOMAIN, hass)
    hass.data[DATA_COMPONENT] = entity_component
    async_setup_conversation_http(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
