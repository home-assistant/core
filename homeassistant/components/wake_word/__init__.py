"""Provide functionality to wake word."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .models import DetectionResult, WakeWord

__all__ = [
    "async_default_engine",
    "async_get_wake_word_detection_entity",
    "DetectionResult",
    "DOMAIN",
    "WakeWord",
    "WakeWordDetectionEntity",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def async_default_engine(hass: HomeAssistant) -> str | None:
    """Return the domain or entity id of the default engine."""
    return next(iter(hass.states.async_entity_ids(DOMAIN)), None)


@callback
def async_get_wake_word_detection_entity(
    hass: HomeAssistant, entity_id: str
) -> WakeWordDetectionEntity | None:
    """Return wwd entity."""
    component: EntityComponent = hass.data[DOMAIN]

    return component.get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up STT."""
    component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)
    component.register_shutdown()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class WakeWordDetectionEntity(RestoreEntity):
    """Represent a single WWD provider."""

    _attr_should_poll = False

    @property
    @abstractmethod
    def supported_wake_words(self) -> list[WakeWord]:
        """Return a list of supported wake words."""

    @abstractmethod
    async def async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]]
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """
