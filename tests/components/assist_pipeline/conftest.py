"""Test fixtures for voice assistant."""

from __future__ import annotations

from collections.abc import AsyncIterable, Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components import stt, tts, wake_word
from homeassistant.components.assist_pipeline import DOMAIN, select as assist_select
from homeassistant.components.assist_pipeline.pipeline import (
    PipelineData,
    PipelineStorageCollection,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
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

_TRANSCRIPT = "test transcript"


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


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
    _supported_options = ["voice", "age", tts.ATTR_AUDIO_OUTPUT]

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
        return self._supported_options

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
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


class MockWakeWordEntity(wake_word.WakeWordDetectionEntity):
    """Mock wake word entity."""

    fail_process_audio = False
    url_path = "wake_word.test"
    _attr_name = "test"

    alternate_detections = False
    detected_wake_word_index = 0

    async def get_supported_wake_words(self) -> list[wake_word.WakeWord]:
        """Return a list of supported wake words."""
        return [
            wake_word.WakeWord(id="test_ww", name="Test Wake Word"),
            wake_word.WakeWord(id="test_ww_2", name="Test Wake Word 2"),
        ]

    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> wake_word.DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps."""
        wake_words = await self.get_supported_wake_words()

        if self.alternate_detections:
            detected_id = wake_words[self.detected_wake_word_index].id
            detected_name = wake_words[self.detected_wake_word_index].name
            self.detected_wake_word_index = (self.detected_wake_word_index + 1) % len(
                wake_words
            )
        else:
            detected_id = wake_words[0].id
            detected_name = wake_words[0].name

        async for chunk, timestamp in stream:
            if chunk.startswith(b"wake word"):
                return wake_word.DetectionResult(
                    wake_word_id=detected_id,
                    wake_word_phrase=detected_name,
                    timestamp=timestamp,
                    queued_audio=[(b"queued audio", 0)],
                )

        # Not detected
        return None


class MockWakeWordEntity2(wake_word.WakeWordDetectionEntity):
    """Second mock wake word entity to test cooldown."""

    fail_process_audio = False
    url_path = "wake_word.test2"
    _attr_name = "test2"

    async def get_supported_wake_words(self) -> list[wake_word.WakeWord]:
        """Return a list of supported wake words."""
        return [wake_word.WakeWord(id="test_ww", name="Test Wake Word")]

    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> wake_word.DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps."""
        wake_words = await self.get_supported_wake_words()

        async for chunk, timestamp in stream:
            if chunk.startswith(b"wake word"):
                return wake_word.DetectionResult(
                    wake_word_id=wake_words[0].id,
                    wake_word_phrase=wake_words[0].name,
                    timestamp=timestamp,
                    queued_audio=[(b"queued audio", 0)],
                )

        # Not detected
        return None


@pytest.fixture
async def mock_wake_word_provider_entity(hass) -> MockWakeWordEntity:
    """Mock wake word provider."""
    return MockWakeWordEntity()


@pytest.fixture
async def mock_wake_word_provider_entity2(hass) -> MockWakeWordEntity2:
    """Mock wake word provider."""
    return MockWakeWordEntity2()


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
    mock_wake_word_provider_entity: MockWakeWordEntity,
    mock_wake_word_provider_entity2: MockWakeWordEntity2,
    config_flow_fixture,
):
    """Initialize relevant components with empty configs."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.STT, Platform.WAKE_WORD]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_unload_platforms(
            config_entry, [Platform.STT, Platform.WAKE_WORD]
        )
        return True

    async def async_setup_entry_stt_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test stt platform via config entry."""
        async_add_entities([mock_stt_provider_entity])

    async def async_setup_entry_wake_word_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test wake word platform via config entry."""
        async_add_entities(
            [mock_wake_word_provider_entity, mock_wake_word_provider_entity2]
        )

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
    mock_platform(
        hass,
        "test.wake_word",
        MockPlatform(
            async_setup_entry=async_setup_entry_wake_word_platform,
        ),
    )
    mock_platform(hass, "test.config_flow")

    assert await async_setup_component(hass, "homeassistant", {})
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
async def assist_device(hass: HomeAssistant, init_components) -> dr.DeviceEntry:
    """Create an assist device."""
    config_entry = MockConfigEntry(domain="test_assist_device")
    config_entry.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        name="Test Device",
        config_entry_id=config_entry.entry_id,
        identifiers={("test_assist_device", "test")},
    )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.SELECT]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_unload_platforms(
            config_entry, [Platform.SELECT]
        )
        return True

    async def async_setup_entry_select_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test select platform via config entry."""
        entities = [
            assist_select.AssistPipelineSelect(
                hass, "test_assist_device", "test-prefix"
            ),
            assist_select.VadSensitivitySelect(hass, "test-prefix"),
        ]
        for ent in entities:
            ent._attr_device_info = dr.DeviceInfo(
                identifiers={("test_assist_device", "test")},
            )
        async_add_entities(entities)

    mock_integration(
        hass,
        MockModule(
            "test_assist_device",
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )
    mock_platform(
        hass,
        "test_assist_device.select",
        MockPlatform(
            async_setup_entry=async_setup_entry_select_platform,
        ),
    )
    mock_platform(hass, "test_assist_device.config_flow")

    with mock_config_flow("test_assist_device", ConfigFlow):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return device


@pytest.fixture
def pipeline_data(hass: HomeAssistant, init_components) -> PipelineData:
    """Return pipeline data."""
    return hass.data[DOMAIN]


@pytest.fixture
def pipeline_storage(pipeline_data) -> PipelineStorageCollection:
    """Return pipeline storage collection."""
    return pipeline_data.pipeline_store
