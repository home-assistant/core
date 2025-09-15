"""Tests for the Google Generative AI Conversation STT entity."""

from __future__ import annotations

from collections.abc import AsyncIterable, Generator
from unittest.mock import AsyncMock, Mock, patch

from google.genai import types
import pytest

from homeassistant.components import stt
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DEFAULT_STT_PROMPT,
    DOMAIN,
    RECOMMENDED_STT_MODEL,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import API_ERROR_500, CLIENT_ERROR_BAD_REQUEST

from tests.common import MockConfigEntry

TEST_CHAT_MODEL = "models/gemini-2.5-flash"
TEST_PROMPT = "Please transcribe the audio."


async def _async_get_audio_stream(data: bytes) -> AsyncIterable[bytes]:
    """Yield the audio data."""
    yield data


@pytest.fixture
def mock_genai_client() -> Generator[AsyncMock]:
    """Mock genai.Client."""
    client = Mock()
    client.aio.models.get = AsyncMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=types.GenerateContentResponse(
            candidates=[
                {
                    "content": {
                        "parts": [{"text": "This is a test transcription."}],
                        "role": "model",
                    }
                }
            ]
        )
    )
    with patch(
        "homeassistant.components.google_generative_ai_conversation.Client",
        return_value=client,
    ) as mock_client:
        yield mock_client.return_value


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Set up the test environment."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "bla"}, version=2, minor_version=1
    )
    config_entry.add_to_hass(hass)

    sub_entry = ConfigSubentry(
        data={
            CONF_CHAT_MODEL: TEST_CHAT_MODEL,
            CONF_PROMPT: TEST_PROMPT,
        },
        subentry_type="stt",
        title="Google AI STT",
        unique_id=None,
    )

    config_entry.runtime_data = mock_genai_client

    hass.config_entries.async_add_subentry(config_entry, sub_entry)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_integration")
async def test_stt_entity_properties(hass: HomeAssistant) -> None:
    """Test STT entity properties."""
    entity: stt.SpeechToTextEntity = hass.data[stt.DOMAIN].get_entity(
        "stt.google_ai_stt"
    )
    assert entity is not None
    assert isinstance(entity.supported_languages, list)
    assert stt.AudioFormats.WAV in entity.supported_formats
    assert stt.AudioFormats.OGG in entity.supported_formats
    assert stt.AudioCodecs.PCM in entity.supported_codecs
    assert stt.AudioCodecs.OPUS in entity.supported_codecs
    assert stt.AudioBitRates.BITRATE_16 in entity.supported_bit_rates
    assert stt.AudioSampleRates.SAMPLERATE_16000 in entity.supported_sample_rates
    assert stt.AudioChannels.CHANNEL_MONO in entity.supported_channels


@pytest.mark.parametrize(
    ("audio_format", "call_convert_to_wav"),
    [
        (stt.AudioFormats.WAV, True),
        (stt.AudioFormats.OGG, False),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_success(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    audio_format: stt.AudioFormats,
    call_convert_to_wav: bool,
) -> None:
    """Test STT processing audio stream successfully."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=audio_format,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    with patch(
        "homeassistant.components.google_generative_ai_conversation.stt.convert_to_wav",
        return_value=b"converted_wav_bytes",
    ) as mock_convert_to_wav:
        result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "This is a test transcription."

    if call_convert_to_wav:
        mock_convert_to_wav.assert_called_once_with(
            b"test_audio_bytes", "audio/L16;rate=16000"
        )
    else:
        mock_convert_to_wav.assert_not_called()

    mock_genai_client.aio.models.generate_content.assert_called_once()
    call_args = mock_genai_client.aio.models.generate_content.call_args
    assert call_args.kwargs["model"] == TEST_CHAT_MODEL

    contents = call_args.kwargs["contents"]
    assert contents[0] == TEST_PROMPT
    assert isinstance(contents[1], types.Part)
    assert contents[1].inline_data.mime_type == f"audio/{audio_format.value}"
    if call_convert_to_wav:
        assert contents[1].inline_data.data == b"converted_wav_bytes"
    else:
        assert contents[1].inline_data.data == b"test_audio_bytes"


@pytest.mark.parametrize(
    "side_effect",
    [
        API_ERROR_500,
        CLIENT_ERROR_BAD_REQUEST,
        ValueError("Test value error"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_api_error(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test STT processing audio stream with API errors."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")
    mock_genai_client.aio.models.generate_content.side_effect = side_effect

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


@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_empty_response(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test STT processing with an empty response from the API."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")
    mock_genai_client.aio.models.generate_content.return_value = (
        types.GenerateContentResponse(candidates=[])
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


@pytest.mark.usefixtures("mock_genai_client")
async def test_stt_uses_default_prompt(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test that the default prompt is used if none is configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "bla"}, version=2, minor_version=1
    )
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = mock_genai_client

    # Subentry with no prompt
    sub_entry = ConfigSubentry(
        data={CONF_CHAT_MODEL: TEST_CHAT_MODEL},
        subentry_type="stt",
        title="Google AI STT",
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(config_entry, sub_entry)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    await entity.async_process_audio_stream(metadata, audio_stream)

    call_args = mock_genai_client.aio.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert contents[0] == DEFAULT_STT_PROMPT


@pytest.mark.usefixtures("mock_genai_client")
async def test_stt_uses_default_model(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test that the default model is used if none is configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "bla"}, version=2, minor_version=1
    )
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = mock_genai_client

    # Subentry with no model
    sub_entry = ConfigSubentry(
        data={CONF_PROMPT: TEST_PROMPT},
        subentry_type="stt",
        title="Google AI STT",
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(config_entry, sub_entry)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")

    metadata = stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    await entity.async_process_audio_stream(metadata, audio_stream)

    call_args = mock_genai_client.aio.models.generate_content.call_args
    assert call_args.kwargs["model"] == RECOMMENDED_STT_MODEL
