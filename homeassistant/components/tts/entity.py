"""Entity for Text-to-Speech."""

from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, final

from propcache.api import cached_property

from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import TtsAudioType
from .media_source import generate_media_source_id
from .models import Voice

CACHED_PROPERTIES_WITH_ATTR_ = {
    "default_language",
    "default_options",
    "supported_languages",
    "supported_options",
}


@dataclass
class TTSAudioRequest:
    """Request to get TTS audio."""

    language: str
    options: dict[str, Any]
    message_gen: AsyncGenerator[str]


@dataclass
class TTSAudioResponse:
    """Response containing TTS audio stream."""

    extension: str
    data_gen: AsyncGenerator[bytes]


class TextToSpeechEntity(RestoreEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Represent a single TTS engine."""

    _attr_should_poll = False
    __last_tts_loaded: str | None = None

    _attr_default_language: str
    _attr_default_options: Mapping[str, Any] | None = None
    _attr_supported_languages: list[str]
    _attr_supported_options: list[str] | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self.__last_tts_loaded is None:
            return None
        return self.__last_tts_loaded

    @cached_property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._attr_supported_languages

    @cached_property
    def default_language(self) -> str:
        """Return the default language."""
        return self._attr_default_language

    @cached_property
    def supported_options(self) -> list[str] | None:
        """Return a list of supported options like voice, emotions."""
        return self._attr_supported_options

    @cached_property
    def default_options(self) -> Mapping[str, Any] | None:
        """Return a mapping with the default options."""
        return self._attr_default_options

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        return None

    async def async_internal_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_internal_added_to_hass()
        try:
            _ = self.default_language
        except AttributeError as err:
            raise AttributeError(
                "TTS entities must either set the '_attr_default_language' attribute or override the 'default_language' property"
            ) from err
        try:
            _ = self.supported_languages
        except AttributeError as err:
            raise AttributeError(
                "TTS entities must either set the '_attr_supported_languages' attribute or override the 'supported_languages' property"
            ) from err
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_tts_loaded = state.state

    async def async_speak(
        self,
        media_player_entity_id: list[str],
        message: str,
        cache: bool,
        language: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Speak via a Media Player."""
        await self.hass.services.async_call(
            DOMAIN_MP,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_entity_id,
                ATTR_MEDIA_CONTENT_ID: generate_media_source_id(
                    self.hass,
                    message=message,
                    engine=self.entity_id,
                    language=language,
                    options=options,
                    cache=cache,
                ),
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_ANNOUNCE: True,
            },
            blocking=True,
            context=self._context,
        )

    @final
    async def internal_async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Process an audio stream to TTS service.

        Only streaming content is allowed!
        """
        self.__last_tts_loaded = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        return await self.async_stream_tts_audio(request)

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse:
        """Generate speech from an incoming message.

        The default implementation is backwards compatible with async_get_tts_audio.
        """
        message = "".join([chunk async for chunk in request.message_gen])
        extension, data = await self.async_get_tts_audio(
            message, request.language, request.options
        )

        if extension is None or data is None:
            raise HomeAssistantError(f"No TTS from {self.entity_id} for '{message}'")

        async def data_gen() -> AsyncGenerator[bytes]:
            yield data

        return TTSAudioResponse(extension, data_gen())

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine."""
        raise NotImplementedError

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Load tts audio file from the engine.

        Return a tuple of file extension and data as bytes.
        """
        return await self.hass.async_add_executor_job(
            partial(self.get_tts_audio, message, language, options=options)
        )
