"""Provide functionality to STT."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import AsyncIterable
from dataclasses import asdict
import logging
from typing import Any, final

from aiohttp import web
from aiohttp.hdrs import istr
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPUnsupportedMediaType,
)

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DATA_PROVIDERS,
    DOMAIN,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResultState,
)
from .legacy import (
    Provider,
    SpeechMetadata,
    SpeechResult,
    async_get_provider,
    async_setup_legacy,
)

__all__ = [
    "async_get_provider",
    "async_get_speech_to_text_entity",
    "AudioBitRates",
    "AudioChannels",
    "AudioCodecs",
    "AudioFormats",
    "AudioSampleRates",
    "DOMAIN",
    "Provider",
    "SpeechToTextEntity",
    "SpeechMetadata",
    "SpeechResult",
    "SpeechResultState",
]

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_speech_to_text_entity(
    hass: HomeAssistant, entity_id: str
) -> SpeechToTextEntity | None:
    """Return stt entity."""
    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]

    return component.get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up STT."""
    component = hass.data[DOMAIN] = EntityComponent[SpeechToTextEntity](
        _LOGGER, DOMAIN, hass
    )

    component.register_shutdown()
    platform_setups = async_setup_legacy(hass, config)

    if platform_setups:
        await asyncio.wait([asyncio.create_task(setup) for setup in platform_setups])

    hass.http.register_view(SpeechToTextView(hass.data[DATA_PROVIDERS]))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class SpeechToTextEntity(RestoreEntity):
    """Represent a single STT provider."""

    _attr_should_poll = False
    __last_processed: str | None = None

    @property
    @final
    def name(self) -> str:
        """Return the name of the provider entity."""
        # Only one entity is allowed per platform for now.
        if self.platform is None:
            raise RuntimeError("Entity is not added to hass yet.")

        return self.platform.platform_name

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the provider entity."""
        if self.__last_processed is None:
            return None
        return self.__last_processed

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""

    @property
    @abstractmethod
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""

    @property
    @abstractmethod
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""

    @property
    @abstractmethod
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""

    @property
    @abstractmethod
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""

    async def async_internal_added_to_hass(self) -> None:
        """Call when the provider entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_processed = state.state

    @final
    async def internal_async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service.

        Only streaming content is allowed!
        """
        self.__last_processed = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        return await self.async_process_audio_stream(metadata=metadata, stream=stream)

    @abstractmethod
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service.

        Only streaming content is allowed!
        """

    @callback
    def check_metadata(self, metadata: SpeechMetadata) -> bool:
        """Check if given metadata supported by this provider."""
        if (
            metadata.language not in self.supported_languages
            or metadata.format not in self.supported_formats
            or metadata.codec not in self.supported_codecs
            or metadata.bit_rate not in self.supported_bit_rates
            or metadata.sample_rate not in self.supported_sample_rates
            or metadata.channel not in self.supported_channels
        ):
            return False
        return True


class SpeechToTextView(HomeAssistantView):
    """STT view to generate a text from audio stream."""

    _legacy_provider_reported = False
    requires_auth = True
    url = "/api/stt/{provider}"
    name = "api:stt:provider"

    def __init__(self, providers: dict[str, Provider]) -> None:
        """Initialize a tts view."""
        self.providers = providers

    async def post(self, request: web.Request, provider: str) -> web.Response:
        """Convert Speech (audio) to text."""
        hass: HomeAssistant = request.app["hass"]
        provider_entity: SpeechToTextEntity | None = None
        if (
            not (
                provider_entity := async_get_speech_to_text_entity(
                    hass, f"{DOMAIN}.{provider}"
                )
            )
            and provider not in self.providers
        ):
            raise HTTPNotFound()

        # Get metadata
        try:
            metadata = _metadata_from_header(request)
        except ValueError as err:
            raise HTTPBadRequest(text=str(err)) from err

        if not provider_entity:
            stt_provider = self._get_provider(provider)

            # Check format
            if not stt_provider.check_metadata(metadata):
                raise HTTPUnsupportedMediaType()

            # Process audio stream
            result = await stt_provider.async_process_audio_stream(
                metadata, request.content
            )
        else:
            # Check format
            if not provider_entity.check_metadata(metadata):
                raise HTTPUnsupportedMediaType()

            # Process audio stream
            result = await provider_entity.internal_async_process_audio_stream(
                metadata, request.content
            )

        # Return result
        return self.json(asdict(result))

    async def get(self, request: web.Request, provider: str) -> web.Response:
        """Return provider specific audio information."""
        hass: HomeAssistant = request.app["hass"]
        if (
            not (
                provider_entity := async_get_speech_to_text_entity(
                    hass, f"{DOMAIN}.{provider}"
                )
            )
            and provider not in self.providers
        ):
            raise HTTPNotFound()

        if not provider_entity:
            stt_provider = self._get_provider(provider)

            return self.json(
                {
                    "languages": stt_provider.supported_languages,
                    "formats": stt_provider.supported_formats,
                    "codecs": stt_provider.supported_codecs,
                    "sample_rates": stt_provider.supported_sample_rates,
                    "bit_rates": stt_provider.supported_bit_rates,
                    "channels": stt_provider.supported_channels,
                }
            )

        return self.json(
            {
                "languages": provider_entity.supported_languages,
                "formats": provider_entity.supported_formats,
                "codecs": provider_entity.supported_codecs,
                "sample_rates": provider_entity.supported_sample_rates,
                "bit_rates": provider_entity.supported_bit_rates,
                "channels": provider_entity.supported_channels,
            }
        )

    def _get_provider(self, provider: str) -> Provider:
        """Get provider.

        Method for legacy providers.
        This can be removed when we remove the legacy provider support.
        """
        stt_provider = self.providers[provider]

        if not self._legacy_provider_reported:
            self._legacy_provider_reported = True
            report_issue = self._suggest_report_issue(provider, stt_provider)
            # This should raise in Home Assistant Core 2023.9
            _LOGGER.warning(
                "Provider %s (%s) is using a legacy implementation, "
                "and should be updated to use the SpeechToTextEntity. Please "
                "%s",
                provider,
                type(stt_provider),
                report_issue,
            )

        return stt_provider

    def _suggest_report_issue(self, provider: str, provider_instance: object) -> str:
        """Suggest to report an issue."""
        report_issue = ""
        if "custom_components" in type(provider_instance).__module__:
            report_issue = "report it to the custom integration author."
        else:
            report_issue = (
                "create a bug report at "
                "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
            )
            report_issue += f"+label%3A%22integration%3A+{provider}%22"

        return report_issue


def _metadata_from_header(request: web.Request) -> SpeechMetadata:
    """Extract STT metadata from header.

    X-Speech-Content:
        format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=de_de
    """
    try:
        data = request.headers[istr("X-Speech-Content")].split(";")
    except KeyError as err:
        raise ValueError("Missing X-Speech-Content header") from err

    fields = (
        "language",
        "format",
        "codec",
        "bit_rate",
        "sample_rate",
        "channel",
    )

    # Convert Header data
    args: dict[str, Any] = {}
    for entry in data:
        key, _, value = entry.strip().partition("=")
        if key not in fields:
            raise ValueError(f"Invalid field: {key}")
        args[key] = value

    for field in fields:
        if field not in args:
            raise ValueError(f"Missing {field} in X-Speech-Content header")

    try:
        return SpeechMetadata(
            language=args["language"],
            format=args["format"],
            codec=args["codec"],
            bit_rate=args["bit_rate"],
            sample_rate=args["sample_rate"],
            channel=args["channel"],
        )
    except ValueError as err:
        raise ValueError(f"Wrong format of X-Speech-Content: {err}") from err
