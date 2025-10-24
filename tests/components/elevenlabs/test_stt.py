"""Tests for the ElevenLabs STT integration."""

from unittest.mock import AsyncMock

from elevenlabs.core import ApiError
import pytest

from homeassistant.components import stt
from homeassistant.components.elevenlabs.const import (
    CONF_MODEL,
    CONF_STT_AUTO_LANGUAGE,
    CONF_VOICE,
)
from homeassistant.core import HomeAssistant

# === Fixtures ===


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


# === SUCCESS TESTS ===


async def test_stt_transcription_success(
    hass: HomeAssistant,
    setup: AsyncMock,
    default_metadata: stt.SpeechMetadata,
    two_chunk_stream,
) -> None:
    """Test successful transcription with valid PCM/WAV input."""
    entity = stt.async_get_speech_to_text_engine(hass, "stt.elevenlabs_speech_to_text")
    assert entity is not None
    result = await entity.async_process_audio_stream(
        default_metadata, two_chunk_stream()
    )
    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "hello world"
    entity._client.speech_to_text.convert.assert_called_once()


@pytest.mark.parametrize(
    "config_options",
    [
        {
            CONF_VOICE: "voice1",
            CONF_MODEL: "model1",
            CONF_STT_AUTO_LANGUAGE: True,
        }
    ],
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
    entity = stt.async_get_speech_to_text_engine(hass, "stt.elevenlabs_speech_to_text")
    assert entity is not None
    result = await entity.async_process_audio_stream(metadata, simple_stream())
    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "hello world"
    entity._client.speech_to_text.convert.assert_called_once()


# === ERROR CASES (PARAMETRIZED) ===


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
    entity = stt.async_get_speech_to_text_engine(hass, "stt.elevenlabs_speech_to_text")
    assert entity is not None
    metadata = request.getfixturevalue(metadata_fixture)
    stream = request.getfixturevalue(stream_fixture)
    assert not entity._auto_detect_language
    result = await entity.async_process_audio_stream(metadata, stream())
    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


async def test_stt_convert_api_error(
    hass: HomeAssistant,
    setup: AsyncMock,
    default_metadata: stt.SpeechMetadata,
    simple_stream,
) -> None:
    """Test that API errors during convert are handled properly."""
    entity = stt.async_get_speech_to_text_engine(hass, "stt.elevenlabs_speech_to_text")
    assert entity is not None
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
    entity = stt.async_get_speech_to_text_engine(hass, "stt.elevenlabs_speech_to_text")
    assert entity is not None
    assert set(entity.supported_formats) == {stt.AudioFormats.WAV, stt.AudioFormats.OGG}
    assert set(entity.supported_codecs) == {stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS}
    assert set(entity.supported_bit_rates) == {stt.AudioBitRates.BITRATE_16}
    assert set(entity.supported_sample_rates) == {stt.AudioSampleRates.SAMPLERATE_16000}
    assert set(entity.supported_channels) == {
        stt.AudioChannels.CHANNEL_MONO,
        stt.AudioChannels.CHANNEL_STEREO,
    }
    assert "en-US" in entity.supported_languages
