"""Test STT platform of OpenAI Conversation integration."""

from collections.abc import AsyncIterable
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from openai import RateLimitError
import pytest

from homeassistant.components import stt
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def _async_get_audio_stream(data: bytes) -> AsyncIterable[bytes]:
    """Yield the audio data."""
    yield data


@pytest.mark.usefixtures("mock_init_component")
async def test_stt_entity_properties(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test STT entity properties."""
    entity: stt.SpeechToTextEntity = hass.data[stt.DOMAIN].get_entity("stt.openai_stt")
    assert entity is not None
    assert isinstance(entity.supported_languages, list)
    assert len(entity.supported_languages)
    assert stt.AudioFormats.WAV in entity.supported_formats
    assert stt.AudioFormats.OGG in entity.supported_formats
    assert stt.AudioCodecs.PCM in entity.supported_codecs
    assert stt.AudioCodecs.OPUS in entity.supported_codecs
    assert stt.AudioBitRates.BITRATE_8 in entity.supported_bit_rates
    assert stt.AudioBitRates.BITRATE_16 in entity.supported_bit_rates
    assert stt.AudioBitRates.BITRATE_24 in entity.supported_bit_rates
    assert stt.AudioBitRates.BITRATE_32 in entity.supported_bit_rates
    assert stt.AudioSampleRates.SAMPLERATE_8000 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_11000 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_16000 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_18900 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_22000 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_32000 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_37800 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_44100 in entity.supported_sample_rates
    assert stt.AudioSampleRates.SAMPLERATE_48000 in entity.supported_sample_rates
    assert stt.AudioChannels.CHANNEL_MONO in entity.supported_channels
    assert stt.AudioChannels.CHANNEL_STEREO in entity.supported_channels


@pytest.mark.usefixtures("mock_init_component")
async def test_stt_process_audio_stream_success_wav(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_transcription: AsyncMock,
) -> None:
    """Test STT processing audio stream successfully."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.openai_stt")
    mock_create_transcription.return_value = "This is a test transcription."

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    wav_buffer = None
    mock_wf = MagicMock()
    mock_wf.writeframes.side_effect = lambda data: wav_buffer.write(
        b"converted_wav_bytes"
    )

    def mock_open(buffer, mode):
        nonlocal wav_buffer
        wav_buffer = buffer
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_wf
        return mock_cm

    with patch(
        "homeassistant.components.openai_conversation.stt.wave.open",
        side_effect=mock_open,
    ) as mock_wave_open:
        result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "This is a test transcription."

    mock_wave_open.assert_called_once()
    mock_wf.setnchannels.assert_called_once_with(1)
    mock_wf.setsampwidth.assert_called_once_with(2)
    mock_wf.setframerate.assert_called_once_with(16000)

    mock_create_transcription.assert_called_once()
    call_args = mock_create_transcription.call_args
    assert call_args.kwargs["model"] == "gpt-4o-mini-transcribe"

    contents = call_args.kwargs["file"]
    assert contents[0].endswith(".wav")
    assert contents[1] == b"converted_wav_bytes"


@pytest.mark.usefixtures("mock_init_component")
async def test_stt_process_audio_stream_success_ogg(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_transcription: AsyncMock,
) -> None:
    """Test STT processing audio stream successfully."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.openai_stt")
    mock_create_transcription.return_value = "This is a test transcription."

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    wav_buffer = None
    mock_wf = MagicMock()
    mock_wf.writeframes.side_effect = lambda data: wav_buffer.write(
        b"converted_wav_bytes"
    )

    def mock_open(buffer, mode):
        nonlocal wav_buffer
        wav_buffer = buffer
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_wf
        return mock_cm

    with patch(
        "homeassistant.components.openai_conversation.stt.wave.open",
        side_effect=mock_open,
    ) as mock_wave_open:
        result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "This is a test transcription."

    mock_wave_open.assert_not_called()

    mock_create_transcription.assert_called_once()
    call_args = mock_create_transcription.call_args
    assert call_args.kwargs["model"] == "gpt-4o-mini-transcribe"

    contents = call_args.kwargs["file"]
    assert contents[0].endswith(".ogg")
    assert contents[1] == b"test_audio_bytes"


@pytest.mark.usefixtures("mock_init_component")
async def test_stt_process_audio_stream_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_transcription: AsyncMock,
) -> None:
    """Test STT processing audio stream with API errors."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.openai_stt")
    mock_create_transcription.side_effect = RateLimitError(
        response=httpx.Response(status_code=429, request=""),
        body=None,
        message=None,
    )

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


@pytest.mark.usefixtures("mock_init_component")
async def test_stt_process_audio_stream_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_transcription: AsyncMock,
) -> None:
    """Test STT processing with an empty response from the API."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.openai_stt")
    mock_create_transcription.return_value = ""

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
