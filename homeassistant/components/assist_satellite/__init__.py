"""Base class for assist satellite entities."""

import logging

import voluptuous as vol

from homeassistant.components import assist_pipeline
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
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
    SatelliteCapabilities,
    SatelliteConfig,
)

__all__ = [
    "DOMAIN",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteState",
    "AssistSatelliteEntity",
    "SatelliteConfig",
    "SatelliteCapabilities",
    "PipelineRunConfig",
    "PipelineRunResult",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE

ATTR_WAKE_WORDS = "wake_words"
ATTR_PROCESS = "process"
ATTR_ANNOUNCE_TEXT = "announce_text"
ATTR_MUTED = "is_muted"

SERVICE_WAIT_WAKE = "wait_wake"
SERVICE_GET_TEXT = "get_text"
SERVICE_SAY_TEXT = "say_text"
SERVICE_MUTE_MICROPHONE = "mute_microphone"


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
        func=async_service_wait_wake,
        required_features=[AssistSatelliteEntityFeature.TRIGGER],
        supports_response=SupportsResponse.OPTIONAL,
    )

    component.async_register_entity_service(
        name=SERVICE_GET_TEXT,
        schema=cv.make_entity_service_schema(
            {
                vol.Optional(ATTR_PROCESS): cv.boolean,
                vol.Optional(ATTR_ANNOUNCE_TEXT): cv.string,
            }
        ),
        func=async_service_get_text,
        required_features=[AssistSatelliteEntityFeature.TRIGGER],
        supports_response=SupportsResponse.OPTIONAL,
    )

    component.async_register_entity_service(
        name=SERVICE_SAY_TEXT,
        schema=cv.make_entity_service_schema(
            {vol.Required(ATTR_ANNOUNCE_TEXT): cv.string}
        ),
        func=async_service_say_text,
        required_features=[AssistSatelliteEntityFeature.TRIGGER],
        supports_response=SupportsResponse.NONE,
    )

    component.async_register_entity_service(
        name=SERVICE_MUTE_MICROPHONE,
        schema=cv.make_entity_service_schema({vol.Required(ATTR_MUTED): cv.boolean}),
        func=async_service_mute_microphone,
        required_features=[AssistSatelliteEntityFeature.AUDIO_INPUT],
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


async def async_service_wait_wake(
    entity: AssistSatelliteEntity, service_call: ServiceCall
) -> str | None:
    """Wait for one or more wake words to be spoken."""
    if announce_text := service_call.data.get(ATTR_ANNOUNCE_TEXT):
        # Announce first
        await entity.async_run_pipeline_on_satellite(
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            run_config=PipelineRunConfig(announce_text=announce_text),
        )

    # Wait for wake word(s)
    result = await entity.async_run_pipeline_on_satellite(
        start_stage=assist_pipeline.PipelineStage.WAKE_WORD,
        end_stage=assist_pipeline.PipelineStage.WAKE_WORD,
        run_config=PipelineRunConfig(
            wake_word_names=service_call.data.get(ATTR_WAKE_WORDS)
        ),
    )

    if (not service_call.return_response) or (result is None):
        return None

    text = result.detected_wake_word or ""
    return text.strip()


async def async_service_get_text(
    entity: AssistSatelliteEntity, service_call: ServiceCall
) -> str | None:
    """Wait for a response from the user."""
    if announce_text := service_call.data.get(ATTR_ANNOUNCE_TEXT):
        # Announce first
        await entity.async_run_pipeline_on_satellite(
            start_stage=assist_pipeline.PipelineStage.TTS,
            end_stage=assist_pipeline.PipelineStage.TTS,
            run_config=PipelineRunConfig(announce_text=announce_text),
        )

    if service_call.data.get(ATTR_PROCESS):
        # Process the spoken text
        end_stage = assist_pipeline.PipelineStage.TTS
    else:
        # Just return the spoken text
        end_stage = assist_pipeline.PipelineStage.STT

    # Wait for response
    result = await entity.async_run_pipeline_on_satellite(
        start_stage=assist_pipeline.PipelineStage.STT,
        end_stage=end_stage,
        run_config=PipelineRunConfig(),
    )

    if (not service_call.return_response) or (result is None):
        return None

    text = result.command_text or ""
    return text.strip()


async def async_service_say_text(
    entity: AssistSatelliteEntity, service_call: ServiceCall
) -> None:
    """Speak text on a satellite."""
    await entity.async_run_pipeline_on_satellite(
        start_stage=assist_pipeline.PipelineStage.TTS,
        end_stage=assist_pipeline.PipelineStage.TTS,
        run_config=PipelineRunConfig(
            announce_text=service_call.data[ATTR_ANNOUNCE_TEXT]
        ),
    )


async def async_service_mute_microphone(
    entity: AssistSatelliteEntity, service_call: ServiceCall
) -> None:
    """Mutes or unmutes the microphone on the satellite."""
    await entity.async_set_microphone_mute(service_call.data[ATTR_MUTED])
