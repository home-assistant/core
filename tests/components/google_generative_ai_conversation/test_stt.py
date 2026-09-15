"""Tests for the Google Generative AI Conversation STT entity."""

from collections.abc import AsyncIterable, Generator
from unittest.mock import AsyncMock, Mock, call, patch

from google.genai import interactions, types
import pytest

from homeassistant.components import stt
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    DEFAULT_STT_PROMPT,
    DOMAIN,
    RECOMMENDED_STT_MODEL,
)
from homeassistant.components.google_generative_ai_conversation.stt import (
    _model_requires_interactions_api,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_PROMPT
from homeassistant.core import HomeAssistant

from . import API_ERROR_500, CLIENT_ERROR_BAD_REQUEST

from tests.common import MockConfigEntry

TEST_CHAT_MODEL = "models/gemini-3.1-flash-lite"
TEST_INTERACTIONS_MODEL = "models/gemini-3.5-transcribe"
TEST_PROMPT = "Please transcribe the audio."


def _interaction_with_text(text: str) -> interactions.Interaction:
    """Build an Interaction whose output_text resolves to the given text."""
    return interactions.Interaction(
        status="completed",
        steps=[
            {
                "type": "model_output",
                "content": [{"type": "text", "text": text}],
            }
        ],
    )


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
    client.aio.interactions.create = AsyncMock(
        return_value=_interaction_with_text("This is a test transcription.")
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
    request: pytest.FixtureRequest,
) -> None:
    """Set up the test environment.

    The chat model defaults to TEST_CHAT_MODEL; override it by indirectly
    parametrizing this fixture.
    """
    model = getattr(request, "param", TEST_CHAT_MODEL)
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "bla"}, version=2, minor_version=1
    )
    config_entry.add_to_hass(hass)

    sub_entry = ConfigSubentry(
        data={
            CONF_CHAT_MODEL: model,
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
    ("model", "expected"),
    [
        pytest.param("models/gemini-3.5-transcribe", True, id="exact"),
        pytest.param(
            "models/gemini-3.5-transcribe-preview", True, id="preview_variant"
        ),
        pytest.param("models/gemini-3.5-transcribe-001", True, id="dated_variant"),
        pytest.param("gemini-3.5-transcribe", True, id="no_models_prefix"),
        pytest.param(TEST_CHAT_MODEL, False, id="regular_chat_model"),
        pytest.param(RECOMMENDED_STT_MODEL, False, id="recommended_stt_model"),
    ],
)
def test_model_requires_interactions_api(model: str, expected: bool) -> None:
    """Test the Interactions-API-only model heuristic."""
    assert _model_requires_interactions_api(model) is expected


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
    mock_genai_client.aio.interactions.create.assert_not_called()
    call_args = mock_genai_client.aio.models.generate_content.call_args
    assert call_args.kwargs["model"] == TEST_CHAT_MODEL

    contents = call_args.kwargs["contents"]
    assert TEST_PROMPT in contents[0]
    assert "en-US" in contents[0]
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


@pytest.mark.parametrize(
    ("setup_integration", "language", "expected_transcription_config"),
    [
        pytest.param(
            TEST_INTERACTIONS_MODEL,
            "en-US",
            {"language_codes": ["en-US"]},
            id="with_language",
        ),
        pytest.param(TEST_INTERACTIONS_MODEL, "", {}, id="without_language"),
    ],
    indirect=["setup_integration"],
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_interactions_success(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    language: str,
    expected_transcription_config: dict[str, list[str]],
) -> None:
    """Test Interactions-API-only models are routed through interactions.create."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")

    metadata = stt.SpeechMetadata(
        language=language,
        format=stt.AudioFormats.OGG,
        codec=stt.AudioCodecs.OPUS,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )
    audio_stream = _async_get_audio_stream(b"test_audio_bytes")

    result = await entity.async_process_audio_stream(metadata, audio_stream)

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "This is a test transcription."

    mock_genai_client.aio.models.generate_content.assert_not_called()
    mock_genai_client.aio.interactions.create.assert_called_once()
    call_kwargs = mock_genai_client.aio.interactions.create.call_args.kwargs

    assert call_kwargs["model"] == TEST_INTERACTIONS_MODEL
    assert "system_instruction" not in call_kwargs
    assert call_kwargs["store"] is False
    assert call_kwargs["stream"] is False

    [audio_content] = call_kwargs["input"]
    assert audio_content["type"] == "audio"
    assert audio_content["data"].read() == b"test_audio_bytes"
    assert audio_content["mime_type"] == "audio/ogg"
    assert "sample_rate" not in audio_content
    assert "channels" not in audio_content

    assert (
        call_kwargs["generation_config"]["transcription_config"]
        == expected_transcription_config
    )


@pytest.mark.parametrize(
    ("audio_format", "expected_convert_calls", "expected_data"),
    [
        pytest.param(
            stt.AudioFormats.WAV,
            [call(b"test_audio_bytes", "audio/L16;rate=16000")],
            b"converted_wav_bytes",
            id="wav",
        ),
        pytest.param(
            stt.AudioFormats.OGG,
            [],
            b"test_audio_bytes",
            id="ogg",
        ),
    ],
)
@pytest.mark.parametrize(
    "setup_integration",
    [pytest.param(TEST_INTERACTIONS_MODEL, id="interactions_model")],
    indirect=True,
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_interactions_audio_format(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    audio_format: stt.AudioFormats,
    expected_convert_calls: list[call],
    expected_data: bytes,
) -> None:
    """Test Interactions-API audio content reflects WAV conversion like generateContent."""
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
    assert mock_convert_to_wav.call_args_list == expected_convert_calls

    call_kwargs = mock_genai_client.aio.interactions.create.call_args.kwargs
    [audio_content] = call_kwargs["input"]
    assert audio_content["mime_type"] == f"audio/{audio_format.value}"
    assert audio_content["data"].read() == expected_data


@pytest.mark.parametrize(
    "setup_integration",
    [pytest.param(TEST_INTERACTIONS_MODEL, id="interactions_model")],
    indirect=True,
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_interactions_error(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test STT logs and returns an error when interactions.create raises."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")
    mock_genai_client.aio.interactions.create.side_effect = RuntimeError(
        "Interactions API unavailable"
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
    assert "Error during STT" in caplog.text


@pytest.mark.parametrize(
    "setup_integration",
    [pytest.param(TEST_INTERACTIONS_MODEL, id="interactions_model")],
    indirect=True,
)
@pytest.mark.usefixtures("setup_integration")
async def test_stt_process_audio_stream_interactions_no_text(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test STT logs the interaction status when there is no output text."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")
    mock_genai_client.aio.interactions.create.return_value = interactions.Interaction(
        status="failed", steps=[]
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
    assert "STT response contained no text (status=failed)" in caplog.text


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
    assert DEFAULT_STT_PROMPT in contents[0]
    assert "en-US" in contents[0]


@pytest.mark.usefixtures("setup_integration")
async def test_stt_includes_language_in_prompt(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test that metadata language is included in the prompt sent to the model."""
    entity = hass.data[stt.DOMAIN].get_entity("stt.google_ai_stt")

    metadata = stt.SpeechMetadata(
        language="he-IL",
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
    prompt = contents[0]
    assert "he-IL" in prompt


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
