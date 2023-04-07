"""Test fixtures for voice assistant."""
from collections.abc import AsyncIterable
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components import stt, tts
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_integration, mock_platform
from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    mock_get_cache_files,
    mock_init_cache_dir,
)

_TRANSCRIPT = "test transcript"


class MockSttProvider(stt.Provider):
    """Mock STT provider."""

    def __init__(self, hass: HomeAssistant, text: str) -> None:
        """Init test provider."""
        self.hass = hass
        self.text = text
        self.received = []

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return ["en-US"]

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bitrates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream."""
        async for data in stream:
            if not data:
                break
            self.received.append(data)
        return stt.SpeechResult(self.text, stt.SpeechResultState.SUCCESS)


class MockTTSProvider(tts.Provider):
    """Mock TTS provider."""

    name = "Test"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return ["en-US"]

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotions."""
        return ["voice", "age"]

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> tts.TtsAudioType:
        """Load TTS data."""
        return ("mp3", b"")


class MockTTS:
    """A mock TTS platform."""

    PLATFORM_SCHEMA = tts.PLATFORM_SCHEMA

    async def async_get_engine(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> tts.Provider:
        """Set up a mock speech component."""
        return MockTTSProvider()


@pytest.fixture
async def mock_stt_provider(hass) -> MockSttProvider:
    """Mock STT provider."""
    return MockSttProvider(hass, _TRANSCRIPT)


@pytest.fixture
async def init_components(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_get_cache_files,  # noqa: F811
    mock_init_cache_dir,  # noqa: F811,
):
    """Initialize relevant components with empty configs."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS())
    mock_platform(
        hass,
        "test.stt",
        Mock(async_get_engine=AsyncMock(return_value=mock_stt_provider)),
    )

    assert await async_setup_component(hass, tts.DOMAIN, {"tts": {"platform": "test"}})
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {"platform": "test"}})
    assert await async_setup_component(hass, "media_source", {})
    assert await async_setup_component(hass, "voice_assistant", {})
