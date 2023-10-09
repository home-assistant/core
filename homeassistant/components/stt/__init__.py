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
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_suggest_report_issue
from homeassistant.util import dt as dt_util, language as language_util

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
    async_default_provider,
    async_get_provider,
    async_setup_legacy,
)
from .models import SpeechMetadata, SpeechResult

__all__ = [
    "async_get_provider",
    "async_get_speech_to_text_engine",
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

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def async_default_engine(hass: HomeAssistant) -> str | None:
    """Return the domain or entity id of the default engine."""
    return async_default_provider(hass) or next(
        iter(hass.states.async_entity_ids(DOMAIN)), None
    )


@callback
def async_get_speech_to_text_entity(
    hass: HomeAssistant, entity_id: str
) -> SpeechToTextEntity | None:
    """Return stt entity."""
    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]

    return component.get_entity(entity_id)


@callback
def async_get_speech_to_text_engine(
    hass: HomeAssistant, engine_id: str
) -> SpeechToTextEntity | Provider | None:
    """Return stt entity or legacy provider."""
    if entity := async_get_speech_to_text_entity(hass, engine_id):
        return entity
    return async_get_provider(hass, engine_id)


@callback
def async_get_speech_to_text_languages(hass: HomeAssistant) -> set[str]:
    """Return a set with the union of languages supported by stt engines."""
    languages = set()

    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]
    legacy_providers: dict[str, Provider] = hass.data[DATA_PROVIDERS]
    for entity in component.entities:
        for language_tag in entity.supported_languages:
            languages.add(language_tag)

    for engine in legacy_providers.values():
        for language_tag in engine.supported_languages:
            languages.add(language_tag)

    return languages


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up STT."""
    websocket_api.async_register_command(hass, websocket_list_engines)

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
            not (provider_entity := async_get_speech_to_text_entity(hass, provider))
            and provider not in self.providers
        ):
            raise HTTPNotFound()

        # Get metadata
        try:
            metadata = _metadata_from_header(request)
        except ValueError as err:
            raise HTTPBadRequest(text=str(err)) from err

        if not provider_entity:
            stt_provider = self._get_provider(hass, provider)

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
            not (provider_entity := async_get_speech_to_text_entity(hass, provider))
            and provider not in self.providers
        ):
            raise HTTPNotFound()

        if not provider_entity:
            stt_provider = self._get_provider(hass, provider)

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

    def _get_provider(self, hass: HomeAssistant, provider: str) -> Provider:
        """Get provider.

        Method for legacy providers.
        This can be removed when we remove the legacy provider support.
        """
        stt_provider = self.providers[provider]

        if not self._legacy_provider_reported:
            self._legacy_provider_reported = True
            report_issue = self._suggest_report_issue(hass, provider, stt_provider)
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

    def _suggest_report_issue(
        self, hass: HomeAssistant, provider: str, provider_instance: object
    ) -> str:
        """Suggest to report an issue."""
        return async_suggest_report_issue(
            hass, integration_domain=provider, module=type(provider_instance).__module__
        )


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


@websocket_api.websocket_command(
    {
        "type": "stt/engine/list",
        vol.Optional("language"): str,
        vol.Optional("country"): str,
    }
)
@callback
def websocket_list_engines(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """List speech-to-text engines and, optionally, if they support a given language."""
    component: EntityComponent[SpeechToTextEntity] = hass.data[DOMAIN]
    legacy_providers: dict[str, Provider] = hass.data[DATA_PROVIDERS]

    country = msg.get("country")
    language = msg.get("language")
    providers = []
    provider_info: dict[str, Any]

    for entity in component.entities:
        provider_info = {
            "engine_id": entity.entity_id,
            "supported_languages": entity.supported_languages,
        }
        if language:
            provider_info["supported_languages"] = language_util.matches(
                language, entity.supported_languages, country
            )
        providers.append(provider_info)

    for engine_id, provider in legacy_providers.items():
        provider_info = {
            "engine_id": engine_id,
            "supported_languages": provider.supported_languages,
        }
        if language:
            provider_info["supported_languages"] = language_util.matches(
                language, provider.supported_languages, country
            )
        providers.append(provider_info)

    connection.send_message(
        websocket_api.result_message(msg["id"], {"providers": providers})
    )
