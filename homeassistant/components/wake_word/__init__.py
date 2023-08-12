"""Provide functionality to wake word."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterable
import logging
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

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
    """Return wake word entity."""
    component: EntityComponent[WakeWordDetectionEntity] = hass.data[DOMAIN]

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
    """Represent a single wake word provider."""

    _attr_should_poll = False
    __last_processed: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self.__last_processed is None:
            return None
        return self.__last_processed

    @property
    @abstractmethod
    def supported_wake_words(self) -> list[WakeWord]:
        """Return a list of supported wake words."""

    @abstractmethod
    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]]
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """

    async def async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]]
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """
        self.__last_processed = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        return await self._async_process_audio_stream(stream)

    async def async_internal_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_processed = state.state
