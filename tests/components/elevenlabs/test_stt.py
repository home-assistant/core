"""Tests for the ElevenLabs STT integration."""

from typing import Any
from unittest.mock import AsyncMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse
import pytest

from homeassistant.components import stt
from homeassistant.components.elevenlabs.const import (
    CONF_MODEL,
    CONF_STT_AUTO_LANGUAGE,
    CONF_VOICE,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import MOCK_MODELS, MOCK_VOICES

from tests.common import MockConfigEntry

# === Fixtures ===


@pytest.fixture(name="config_options_auto_language")
def config_options_auto_language() -> dict:
    """Override default config options with auto language enabled."""
    return {
        CONF_VOICE: "voice1",
        CONF_MODEL: "model1",
        CONF_STT_AUTO_LANGUAGE: True,
    }


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config_data: dict[str, Any],
    config_options: dict[str, Any],
    config_options_auto_language: dict[str, Any],
    request: pytest.FixtureRequest,
    mock_async_client: AsyncMock,
) -> AsyncMock:
    """Set up the STT integration with mocked ElevenLabs client."""

    param = getattr(request, "param", "mock_config_entry_setup")
    if param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, config_data, config_options)
    elif param == "mock_config_entry_setup_auto_language":
        await mock_config_entry_setup(hass, config_data, config_options_auto_language)
    else:
        raise RuntimeError("Invalid setup fixture")

    await hass.async_block_till_done()

    return mock_async_client


@pytest.fixture
def default_metadata() -> stt.SpeechMetadata:
    """Return default metadata for valid PCM WAV input."""
    return stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
        bit_rate=stt.AudioBitRates.BITRATE_16,
    )


# === Stream Fixtures ===


@pytest.fixture
def two_chunk_stream():
    """Return a stream that yields two chunks of audio."""

    async def _stream():
        yield b"chunk1"
        yield b"chunk2"

    return _stream


@pytest.fixture
def simple_stream():
    """Return a basic stream yielding one audio chunk."""

    async def _stream():
        yield b"data"

    return _stream


@pytest.fixture
def empty_stream():
    """Return an empty stream."""

    async def _stream():
        return
        yield  # This makes it an async generator

    return _stream


# === Metadata Fixtures for Edge Cases ===


@pytest.fixture
def unsupported_language_metadata() -> stt.SpeechMetadata:
    """Return metadata with unsupported language code."""
    return stt.SpeechMetadata(
        language="xx-XX",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
        bit_rate=stt.AudioBitRates.BITRATE_16,
    )


@pytest.fixture
def incompatible_pcm_metadata() -> stt.SpeechMetadata:
    """Return metadata that is PCM but not raw-compatible (e.g., stereo)."""
    return stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_STEREO,
        bit_rate=stt.AudioBitRates.BITRATE_16,
    )


@pytest.fixture
def opus_metadata() -> stt.SpeechMetadata:
    """Return valid metadata using OPUS codec."""
    return stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
        bit_rate=stt.AudioBitRates.BITRATE_16,
    )


async def mock_config_entry_setup(
    hass: HomeAssistant, config_data: dict[str, Any], config_options: dict[str, Any]
) -> None:
    """Mock config entry setup."""
    default_config_data = {
        CONF_API_KEY: "api_key",
    }
    default_config_options = {
        CONF_VOICE: "voice1",
        CONF_MODEL: "model1",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=default_config_data | config_data,
        options=default_config_options | config_options,
    )
    config_entry.add_to_hass(hass)
    client_mock = AsyncMock()
    client_mock.voices.get_all.return_value = GetVoicesResponse(voices=MOCK_VOICES)
    client_mock.models.list.return_value = MOCK_MODELS
    stt_mock = AsyncMock()
    stt_mock.convert.return_value = AsyncMock(
        text="hello world", language_code="en", language_probability=0.95
    )
    client_mock.speech_to_text = stt_mock

    with patch(
        "homeassistant.components.elevenlabs.AsyncElevenLabs", return_value=client_mock
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)


# === SUCCESS TESTS ===


async def test_stt_transcription_success(
    hass: HomeAssistant,
    setup: AsyncMock,
    default_metadata: stt.SpeechMetadata,
    two_chunk_stream,
) -> None:
    """Test successful transcription with valid PCM/WAV input."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")
    result = await entity.async_process_audio_stream(
        default_metadata, two_chunk_stream()
    )
    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "hello world"
    entity._client.speech_to_text.convert.assert_called_once()


@pytest.mark.parametrize(
    "setup", ["mock_config_entry_setup_auto_language"], indirect=True
)
async def test_stt_transcription_success_auto_language(
    hass: HomeAssistant,
    setup: AsyncMock,
    simple_stream,
) -> None:
    """Test successful transcription when auto language detection is enabled."""
    metadata = stt.SpeechMetadata(
        language="na",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
        bit_rate=stt.AudioBitRates.BITRATE_16,
    )
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")
    result = await entity.async_process_audio_stream(metadata, simple_stream())
    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "hello world"
    entity._client.speech_to_text.convert.assert_called_once()


# === ERROR CASES (PARAMETRIZED) ===


@pytest.mark.parametrize("config_options", ["config_options_disabled"], indirect=True)
@pytest.mark.parametrize(
    ("metadata_fixture", "stream_fixture"),
    [
        ("unsupported_language_metadata", "simple_stream"),
        ("incompatible_pcm_metadata", "simple_stream"),
        ("opus_metadata", "empty_stream"),
    ],
)
async def test_stt_edge_cases(
    hass: HomeAssistant,
    setup: AsyncMock,
    request: pytest.FixtureRequest,
    metadata_fixture: str,
    stream_fixture: str,
) -> None:
    """Test various error scenarios like unsupported language or bad format."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")
    metadata = request.getfixturevalue(metadata_fixture)
    stream = request.getfixturevalue(stream_fixture)
    assert not entity._auto_detect_language
    result = await entity.async_process_audio_stream(metadata, stream())
    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


async def test_stt_timeout_during_stream(
    hass: HomeAssistant,
    setup: AsyncMock,
    default_metadata: stt.SpeechMetadata,
    simple_stream,
) -> None:
    """Test timeout exception raised when stream is too slow."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")

    async def fake_wait_for(coro, timeout):
        try:
            await coro  # ensure coroutine is awaited to prevent warning
        finally:
            raise TimeoutError

    with patch("asyncio.wait_for", side_effect=fake_wait_for):
        result = await entity.async_process_audio_stream(
            default_metadata, simple_stream()
        )
    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


async def test_stt_convert_api_error(
    hass: HomeAssistant,
    setup: AsyncMock,
    default_metadata: stt.SpeechMetadata,
    simple_stream,
) -> None:
    """Test that API errors during convert are handled properly."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")
    entity._client.speech_to_text.convert.side_effect = ApiError()
    result = await entity.async_process_audio_stream(default_metadata, simple_stream())
    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


# === SUPPORTED PROPERTIES ===


async def test_supported_properties(
    hass: HomeAssistant,
    setup: AsyncMock,
) -> None:
    """Test the advertised capabilities of the ElevenLabs STT entity."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.elevenlabs_speech_to_text")
    assert set(entity.supported_formats) == {stt.AudioFormats.WAV, stt.AudioFormats.OGG}
    assert set(entity.supported_codecs) == {stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS}
    assert set(entity.supported_bit_rates) == {stt.AudioBitRates.BITRATE_16}
    assert set(entity.supported_sample_rates) == {stt.AudioSampleRates.SAMPLERATE_16000}
    assert set(entity.supported_channels) == {
        stt.AudioChannels.CHANNEL_MONO,
        stt.AudioChannels.CHANNEL_STEREO,
    }
    assert "en-US" in entity.supported_languages
