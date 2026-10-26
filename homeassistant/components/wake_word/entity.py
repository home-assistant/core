"""Base entity for the Wake-word detection platform."""

from abc import abstractmethod
from collections.abc import AsyncIterable
from typing import final, override

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .models import DetectionResult, WakeWord


class WakeWordDetectionEntity(RestoreEntity):
    """Represent a single wake word provider."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    __last_detected: str | None = None

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self.__last_detected

    @abstractmethod
    async def get_supported_wake_words(self) -> list[WakeWord]:
        """Return a list of supported wake words."""

    @abstractmethod
    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """

    async def async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """
        result = await self._async_process_audio_stream(stream, wake_word_id)
        if result is not None:
            # Update last detected only when there is a detection
            self.__last_detected = dt_util.utcnow().isoformat()
            self.async_write_ha_state()

        return result

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_detected = state.state
