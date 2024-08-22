"""Base class for assist satellite entities."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .entity import AssistSatelliteEntity
from .models import (
    AssistSatelliteEntityFeature,
    AssistSatelliteState,
    PipelineRunConfig,
    PipelineRunResult,
)

__all__ = [
    "DOMAIN",
    "AssistSatelliteEntity",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteState",
    "PipelineRunConfig",
    "PipelineRunResult",
    "SERVICE_WAIT_WAKE",
    "SERVICE_GET_COMMAND",
    "SERVICE_SAY_TEXT",
    "ATTR_WAKE_WORDS",
    "ATTR_PROCESS",
    "ATTR_ANNOUNCE_TEXT",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE

ATTR_WAKE_WORDS = "wake_words"
ATTR_PROCESS = "process"
ATTR_ANNOUNCE_TEXT = "announce_text"

SERVICE_WAIT_WAKE = "wait_wake"
SERVICE_GET_COMMAND = "get_command"
SERVICE_SAY_TEXT = "say_text"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DOMAIN] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        name=SERVICE_WAIT_WAKE,
        schema=cv.make_entity_service_schema(
            {
                vol.Required(ATTR_WAKE_WORDS): [cv.string],
                vol.Optional(ATTR_ANNOUNCE_TEXT): cv.string,
            }
        ),
        func="async_wait_wake",
        required_features=[AssistSatelliteEntityFeature.TRIGGER_PIPELINE],
        supports_response=SupportsResponse.OPTIONAL,
    )

    component.async_register_entity_service(
        name=SERVICE_GET_COMMAND,
        schema=cv.make_entity_service_schema(
            {
                vol.Optional(ATTR_PROCESS): cv.boolean,
                vol.Optional(ATTR_ANNOUNCE_TEXT): cv.string,
            }
        ),
        func="async_get_command",
        required_features=[AssistSatelliteEntityFeature.TRIGGER_PIPELINE],
        supports_response=SupportsResponse.OPTIONAL,
    )

    component.async_register_entity_service(
        name=SERVICE_SAY_TEXT,
        schema=cv.make_entity_service_schema(
            {vol.Required(ATTR_ANNOUNCE_TEXT): cv.string}
        ),
        func="async_say_text",
        required_features=[AssistSatelliteEntityFeature.TRIGGER_PIPELINE],
        supports_response=SupportsResponse.NONE,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)
