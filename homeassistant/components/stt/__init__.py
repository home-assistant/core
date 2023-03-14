"""Provide functionality to STT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import logging
from typing import Any

from aiohttp import StreamReader, web
from aiohttp.hdrs import istr
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPNotFound,
    HTTPUnsupportedMediaType,
)

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import engine, engine_component
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResultState,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_provider(
    hass: HomeAssistant, provider: str | None = None
) -> Provider | None:
    """Return provider."""
    component: engine_component.EngineComponent[Provider] | None = hass.data.get(DOMAIN)

    if component is None:
        return None

    if provider is None:
        providers = component.async_get_engines()
        return providers[0] if providers else None

    return component.async_get_engine(provider)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up STT."""
    hass.data[DOMAIN] = engine_component.EngineComponent(_LOGGER, DOMAIN, hass, config)
    hass.http.register_view(SpeechToTextView(hass.data[DOMAIN]))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: engine_component.EngineComponent[Provider] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: engine_component.EngineComponent[Provider] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class SpeechMetadata:
    """Metadata of audio stream."""

    language: str
    format: AudioFormats
    codec: AudioCodecs
    bit_rate: AudioBitRates
    sample_rate: AudioSampleRates
    channel: AudioChannels

    def __post_init__(self) -> None:
        """Finish initializing the metadata."""
        self.bit_rate = AudioBitRates(int(self.bit_rate))
        self.sample_rate = AudioSampleRates(int(self.sample_rate))
        self.channel = AudioChannels(int(self.channel))


@dataclass
class SpeechResult:
    """Result of audio Speech."""

    text: str | None
    result: SpeechResultState


class Provider(engine.Engine, ABC):
    """Represent a single STT provider."""

    hass: HomeAssistant | None = None
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

    def __init__(self, engines: engine_component.EngineComponent[Provider]) -> None:
        """Initialize a tts view."""
        self.engines = engines

    async def post(self, request: web.Request, provider: str) -> web.Response:
        """Convert Speech (audio) to text."""
        stt_provider = self.engines.async_get_engine(provider)
        if stt_provider is None:
            raise HTTPNotFound()

        # Get metadata
        try:
            metadata = metadata_from_header(request)
        except ValueError as err:
            raise HTTPBadRequest(text=str(err)) from err

        # Check format
        if not stt_provider.check_metadata(metadata):
            raise HTTPUnsupportedMediaType()

        # Process audio stream
        result = await stt_provider.async_process_audio_stream(
            metadata, request.content
        )

        # Return result
        return self.json(asdict(result))

    async def get(self, request: web.Request, provider: str) -> web.Response:
        """Return provider specific audio information."""
        stt_provider = self.engines.async_get_engine(provider)
        if stt_provider is None:
            raise HTTPNotFound()

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


def metadata_from_header(request: web.Request) -> SpeechMetadata:
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
            raise ValueError(f"Invalid field {key}")
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
    except TypeError as err:
        raise ValueError(f"Wrong format of X-Speech-Content: {err}") from err
