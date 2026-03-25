"""Provide common test tools for STT."""

from __future__ import annotations

from collections.abc import AsyncIterable, Callable, Coroutine
from pathlib import Path
from typing import Any

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockPlatform, mock_platform

TEST_DOMAIN = "test"


class BaseProvider:
    """Mock STT provider."""

    fail_process_audio = False

    def __init__(
        self, *, supported_languages: list[str] | None = None, text: str = "test_result"
    ) -> None:
        """Init test provider."""
        self._supported_languages = supported_languages or ["de", "de-CH", "en"]
        self.calls: list[tuple[SpeechMetadata, AsyncIterable[bytes]]] = []
        self.received: list[bytes] = []
        self.text = text

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream."""
        self.calls.append((metadata, stream))
        async for data in stream:
            if not data:
                break
            self.received.append(data)
        if self.fail_process_audio:
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult(self.text, SpeechResultState.SUCCESS)


class MockSTTProvider(BaseProvider, Provider):
    """Mock provider."""

    url_path = TEST_DOMAIN


class MockSTTProviderEntity(BaseProvider, SpeechToTextEntity):
    """Mock provider entity."""

    url_path = "stt.test"
    _attr_name = "test"


class MockSTTPlatform(MockPlatform):
    """Help to set up test stt service."""

    def __init__(
        self,
        async_get_engine: Callable[
            [HomeAssistant, ConfigType, DiscoveryInfoType | None],
            Coroutine[Any, Any, Provider | None],
        ]
        | None = None,
        get_engine: Callable[
            [HomeAssistant, ConfigType, DiscoveryInfoType | None], Provider | None
        ]
        | None = None,
    ) -> None:
        """Return the stt service."""
        super().__init__()
        if get_engine:
            self.get_engine = get_engine
        if async_get_engine:
            self.async_get_engine = async_get_engine


def mock_stt_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    integration: str = "stt",
    async_get_engine: Callable[
        [HomeAssistant, ConfigType, DiscoveryInfoType | None],
        Coroutine[Any, Any, Provider | None],
    ]
    | None = None,
    get_engine: Callable[
        [HomeAssistant, ConfigType, DiscoveryInfoType | None], Provider | None
    ]
    | None = None,
):
    """Specialize the mock platform for stt."""
    loaded_platform = MockSTTPlatform(async_get_engine, get_engine)
    mock_platform(hass, f"{integration}.stt", loaded_platform)

    return loaded_platform


def mock_stt_entity_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    integration: str,
    async_setup_entry: Callable[
        [HomeAssistant, ConfigEntry, AddEntitiesCallback],
        Coroutine[Any, Any, None],
    ]
    | None = None,
) -> MockPlatform:
    """Specialize the mock platform for stt."""
    loaded_platform = MockPlatform(async_setup_entry=async_setup_entry)
    mock_platform(hass, f"{integration}.stt", loaded_platform)
    return loaded_platform
