"""Provide functionality to STT."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging

from aiohttp import StreamReader, web
from aiohttp.hdrs import istr
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPUnsupportedMediaType,
)
import attr

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_prepare_setup_platform

from .const import (
    DOMAIN,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResultState,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config):
    """Set up STT."""
    providers = {}

    async def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Set up a TTS platform."""
        if p_config is None:
            p_config = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            provider = await platform.async_get_engine(hass, p_config, discovery_info)
            if provider is None:
                _LOGGER.error("Error setting up platform %s", p_type)
                return

            provider.name = p_type
            provider.hass = hass

            providers[provider.name] = provider
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform: %s", p_type)
            return

    setup_tasks = [
        asyncio.create_task(async_setup_platform(p_type, p_config))
        for p_type, p_config in config_per_platform(config, DOMAIN)
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    # Add discovery support
    async def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    hass.http.register_view(SpeechToTextView(providers))
    return True


@attr.s
class SpeechMetadata:
    """Metadata of audio stream."""

    language: str = attr.ib()
    format: AudioFormats = attr.ib()
    codec: AudioCodecs = attr.ib()
    bit_rate: AudioBitRates = attr.ib(converter=int)
    sample_rate: AudioSampleRates = attr.ib(converter=int)
    channel: AudioChannels = attr.ib(converter=int)


@attr.s
class SpeechResult:
    """Result of audio Speech."""

    text: str | None = attr.ib()
    result: SpeechResultState = attr.ib()


class Provider(ABC):
    """Represent a single STT provider."""

    hass: HomeAssistantType | None = None
    name: str | None = None

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

    @abstractmethod
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: StreamReader
    ) -> SpeechResult:
        """Process an audio stream to STT service.

        Only streaming of content are allow!
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

    requires_auth = True
    url = "/api/stt/{provider}"
    name = "api:stt:provider"

    def __init__(self, providers: dict[str, Provider]) -> None:
        """Initialize a tts view."""
        self.providers = providers

    @staticmethod
    def _metadata_from_header(request: web.Request) -> SpeechMetadata | None:
        """Extract metadata from header.

        X-Speech-Content: format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=de_de
        """
        try:
            data = request.headers[istr("X-Speech-Content")].split(";")
        except KeyError:
            _LOGGER.warning("Missing X-Speech-Content")
            return None

        # Convert Header data
        args = {}
        for value in data:
            value = value.strip()
            args[value.partition("=")[0]] = value.partition("=")[2]

        try:
            return SpeechMetadata(**args)
        except TypeError as err:
            _LOGGER.warning("Wrong format of X-Speech-Content: %s", err)
            return None

    async def post(self, request: web.Request, provider: str) -> web.Response:
        """Convert Speech (audio) to text."""
        if provider not in self.providers:
            raise HTTPNotFound()
        stt_provider: Provider = self.providers[provider]

        # Get metadata
        metadata = self._metadata_from_header(request)
        if not metadata:
            raise HTTPBadRequest()

        # Check format
        if not stt_provider.check_metadata(metadata):
            raise HTTPUnsupportedMediaType()

        # Process audio stream
        result = await stt_provider.async_process_audio_stream(
            metadata, request.content
        )

        # Return result
        return self.json(attr.asdict(result))

    async def get(self, request: web.Request, provider: str) -> web.Response:
        """Return provider specific audio information."""
        if provider not in self.providers:
            raise HTTPNotFound()
        stt_provider: Provider = self.providers[provider]

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
