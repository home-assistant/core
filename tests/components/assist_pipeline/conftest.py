"""Test fixtures for voice assistant."""
from __future__ import annotations

from collections.abc import AsyncIterable, Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components import stt, tts
from homeassistant.components.assist_pipeline import DOMAIN
from homeassistant.components.assist_pipeline.pipeline import PipelineStorageCollection
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    init_cache_dir_side_effect,
    mock_get_cache_files,
    mock_init_cache_dir,
)

_TRANSCRIPT = "test transcript"


class BaseProvider:
    """Mock STT provider."""

    _supported_languages = ["en-US"]

    def __init__(self, text: str) -> None:
        """Init test provider."""
        self.text = text
        self.received: list[bytes] = []

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

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


class MockSttProvider(BaseProvider, stt.Provider):
    """Mock provider."""


class MockSttProviderEntity(BaseProvider, stt.SpeechToTextEntity):
    """Mock provider entity."""

    _attr_name = "Mock STT"


class MockTTSProvider(tts.Provider):
    """Mock TTS provider."""

    name = "Test"
    _supported_languages = ["en-US"]
    _supported_voices = {
        "en-US": [
            tts.Voice("james_earl_jones", "James Earl Jones"),
            tts.Voice("fran_drescher", "Fran Drescher"),
        ]
    }

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return self._supported_languages

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice] | None:
        """Return a list of supported voices for a language."""
        return self._supported_voices.get(language)

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotions."""
        return ["voice", "age", tts.ATTR_AUDIO_OUTPUT]

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> tts.TtsAudioType:
        """Load TTS data."""
        return ("mp3", b"")


class MockTTSPlatform(MockPlatform):
    """A mock TTS platform."""

    PLATFORM_SCHEMA = tts.PLATFORM_SCHEMA

    def __init__(self, *, async_get_engine, **kwargs):
        """Initialize the tts platform."""
        super().__init__(**kwargs)
        self.async_get_engine = async_get_engine


@pytest.fixture
async def mock_tts_provider(hass) -> MockTTSProvider:
    """Mock TTS provider."""
    return MockTTSProvider()


@pytest.fixture
async def mock_stt_provider() -> MockSttProvider:
    """Mock STT provider."""
    return MockSttProvider(_TRANSCRIPT)


@pytest.fixture
def mock_stt_provider_entity() -> MockSttProviderEntity:
    """Test provider entity fixture."""
    return MockSttProviderEntity(_TRANSCRIPT)


class MockSttPlatform(MockPlatform):
    """Provide a fake STT platform."""

    def __init__(self, *, async_get_engine, **kwargs):
        """Initialize the stt platform."""
        super().__init__(**kwargs)
        self.async_get_engine = async_get_engine


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, "test.config_flow")

    with mock_config_flow("test", MockFlow):
        yield


@pytest.fixture
async def init_supporting_components(
    hass: HomeAssistant,
    mock_stt_provider: MockSttProvider,
    mock_stt_provider_entity: MockSttProviderEntity,
    mock_tts_provider: MockTTSProvider,
    config_flow_fixture,
    init_cache_dir_side_effect,  # noqa: F811
    mock_get_cache_files,  # noqa: F811
    mock_init_cache_dir,  # noqa: F811
):
    """Initialize relevant components with empty configs."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, stt.DOMAIN)
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_forward_entry_unload(config_entry, stt.DOMAIN)
        return True

    async def async_setup_entry_stt_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test stt platform via config entry."""
        async_add_entities([mock_stt_provider_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )
    mock_platform(
        hass,
        "test.tts",
        MockTTSPlatform(
            async_get_engine=AsyncMock(return_value=mock_tts_provider),
        ),
    )
    mock_platform(
        hass,
        "test.stt",
        MockSttPlatform(
            async_get_engine=AsyncMock(return_value=mock_stt_provider),
            async_setup_entry=async_setup_entry_stt_platform,
        ),
    )
    mock_platform(hass, "test.config_flow")

    assert await async_setup_component(hass, tts.DOMAIN, {"tts": {"platform": "test"}})
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {"platform": "test"}})
    assert await async_setup_component(hass, "media_source", {})

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def init_components(hass: HomeAssistant, init_supporting_components):
    """Initialize relevant components with empty configs."""

    assert await async_setup_component(hass, "assist_pipeline", {})


@pytest.fixture
def pipeline_storage(hass: HomeAssistant, init_components) -> PipelineStorageCollection:
    """Return pipeline storage collection."""
    return hass.data[DOMAIN].pipeline_store
