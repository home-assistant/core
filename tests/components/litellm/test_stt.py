"""Test STT platform of LiteLLM integration."""

from collections.abc import AsyncIterable
import io
from unittest.mock import AsyncMock, MagicMock, patch
import wave

import httpx
from openai import (
    APIConnectionError,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
    omit,
)
import pytest

from homeassistant.components import stt
from homeassistant.components.litellm.const import (
    CONF_STT_CUSTOM_PROMPT_KEYWORDS,
    CONF_STT_KEYWORDS,
    CONF_STT_PROMPT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_URL

from tests.common import MockConfigEntry


async def _audio_stream(*chunks: bytes) -> AsyncIterable[bytes]:
    """Yield audio chunks."""
    for chunk in chunks:
        yield chunk


async def _setup_stt(
    hass: HomeAssistant,
    subentry_options: dict[str, object] | None = None,
) -> stt.SpeechToTextEntity:
    """Set up a LiteLLM STT entity."""
    entry = MockConfigEntry(
        title="localhost:4000",
        domain=DOMAIN,
        data={CONF_URL: TEST_URL, CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MODEL: "home-stt", **(subentry_options or {})},
                subentry_id="STT",
                subentry_type="stt",
                title="home-stt",
                unique_id=None,
            )
        ],
    )
    await setup_integration(hass, entry)

    return next(iter(hass.data[stt.DOMAIN].entities))


def _metadata() -> stt.SpeechMetadata:
    """Return the audio format supported by LiteLLM STT."""
    return stt.SpeechMetadata(
        language="en-US",
        format=stt.AudioFormats.WAV,
        codec=stt.AudioCodecs.PCM,
        bit_rate=stt.AudioBitRates.BITRATE_16,
        sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
        channel=stt.AudioChannels.CHANNEL_MONO,
    )


@pytest.mark.usefixtures("mock_openai_client")
async def test_stt_entity_properties(hass: HomeAssistant) -> None:
    """Test STT entity audio properties."""
    entity = await _setup_stt(hass)

    assert isinstance(entity.supported_languages, list)
    assert "en-US" in entity.supported_languages
    assert "pl-PL" in entity.supported_languages
    assert entity.check_metadata(_metadata())
    assert entity.supported_formats == [stt.AudioFormats.WAV]
    assert entity.supported_codecs == [stt.AudioCodecs.PCM]
    assert entity.supported_bit_rates == [stt.AudioBitRates.BITRATE_16]
    assert entity.supported_sample_rates == [stt.AudioSampleRates.SAMPLERATE_16000]
    assert entity.supported_channels == [stt.AudioChannels.CHANNEL_MONO]


async def test_stt(hass: HomeAssistant, mock_openai_client: AsyncMock) -> None:
    """Test transcription."""
    entity = await _setup_stt(hass)
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Turn on the light")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"first", b"second")
    )

    assert result == stt.SpeechResult(
        "Turn on the light", stt.SpeechResultState.SUCCESS
    )
    call = mock_openai_client.audio.transcriptions.create.call_args.kwargs
    assert call["model"] == "home-stt"
    assert call["language"] == "en"
    assert call["file"][0] == "audio.wav"
    with wave.open(io.BytesIO(call["file"][1]), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000


async def test_stt_passes_prompt_and_keywords(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test passing optional prompt and keyword hints to LiteLLM."""
    entity = await _setup_stt(
        hass,
        {
            CONF_STT_CUSTOM_PROMPT_KEYWORDS: True,
            CONF_STT_PROMPT: "Use the configured names",
            CONF_STT_KEYWORDS: "Alice, Bob, Alice",
        },
    )
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Turn on the light")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result.result is stt.SpeechResultState.SUCCESS
    call = mock_openai_client.audio.transcriptions.create.call_args.kwargs
    assert call["prompt"] == "Use the configured names"
    assert call["keywords"] == ["Alice", "Bob", "Alice"]


async def test_stt_ignores_stale_hints_when_disabled(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test disabled hints do not send stale configured values."""
    entity = await _setup_stt(
        hass,
        {
            CONF_STT_CUSTOM_PROMPT_KEYWORDS: False,
            CONF_STT_PROMPT: "Stale prompt",
            CONF_STT_KEYWORDS: "Stale, keywords",
        },
    )
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Turn on the light")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result.result is stt.SpeechResultState.SUCCESS
    call = mock_openai_client.audio.transcriptions.create.call_args.kwargs
    assert call["prompt"] is omit
    assert call["keywords"] is omit


async def test_stt_renders_prompt_and_keywords_templates(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test rendering optional prompt and keyword templates."""
    hass.states.async_set("sensor.transcription_context", "Alice")
    entity = await _setup_stt(
        hass,
        {
            CONF_STT_CUSTOM_PROMPT_KEYWORDS: True,
            CONF_STT_PROMPT: "Recognize {{ states('sensor.transcription_context') }}",
            CONF_STT_KEYWORDS: "{{ states('sensor.transcription_context') }}, Bob",
        },
    )
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Turn on the light")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result.result is stt.SpeechResultState.SUCCESS
    call = mock_openai_client.audio.transcriptions.create.call_args.kwargs
    assert call["prompt"] == "Recognize Alice"
    assert call["keywords"] == ["Alice", "Bob"]


async def test_stt_template_error(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test a template error returns an STT error."""
    entity = await _setup_stt(
        hass, {CONF_STT_CUSTOM_PROMPT_KEYWORDS: True, CONF_STT_PROMPT: "{{ 1 / 0 }}"}
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result == stt.SpeechResult(None, stt.SpeechResultState.ERROR)
    mock_openai_client.audio.transcriptions.create.assert_not_called()


async def test_stt_empty_response_keeps_entity_available(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test an empty response keeps the proxy available."""
    entity = await _setup_stt(hass)
    coordinator = entity.entry.runtime_data
    coordinator.mark_connection_error()
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result == stt.SpeechResult(None, stt.SpeechResultState.ERROR)
    assert entity.available


async def test_stt_connection_error_marks_entity_unavailable(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test connection errors mark the entity unavailable."""
    entity = await _setup_stt(hass)
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=APIConnectionError(request=None)
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result.result is stt.SpeechResultState.ERROR
    assert not entity.available


@pytest.mark.parametrize("error_cls", [AuthenticationError, PermissionDeniedError])
async def test_stt_auth_error_refreshes_coordinator(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    error_cls: type[AuthenticationError | PermissionDeniedError],
) -> None:
    """Test authentication errors refresh coordinator state."""
    entity = await _setup_stt(hass)
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=error_cls(
            message="invalid api key",
            response=httpx.Response(
                401, request=httpx.Request("POST", "http://localhost")
            ),
            body=None,
        )
    )
    coordinator = entity.entry.runtime_data
    with patch.object(
        coordinator, "async_request_refresh", new_callable=AsyncMock
    ) as refresh:
        result = await entity.async_process_audio_stream(
            _metadata(), _audio_stream(b"audio")
        )

    assert result.result is stt.SpeechResultState.ERROR
    refresh.assert_awaited_once()


async def test_stt_provider_error_keeps_entity_available(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> None:
    """Test provider errors do not mark the proxy unavailable."""
    entity = await _setup_stt(hass)
    mock_openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=OpenAIError("bad request")
    )

    result = await entity.async_process_audio_stream(
        _metadata(), _audio_stream(b"audio")
    )

    assert result.result is stt.SpeechResultState.ERROR
    assert entity.available
