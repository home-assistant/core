"""Test stt."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.error import Error

from homeassistant.components import stt
from homeassistant.core import HomeAssistant

from . import MockAsyncTcpClient


async def test_support(hass: HomeAssistant, init_wyoming_stt) -> None:
    """Test supported properties."""
    state = hass.states.get("stt.test_asr")
    assert state is not None

    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    assert entity.supported_languages == ["en-US"]
    assert entity.supported_formats == [stt.AudioFormats.WAV]
    assert entity.supported_codecs == [stt.AudioCodecs.PCM]
    assert entity.supported_bit_rates == [stt.AudioBitRates.BITRATE_16]
    assert entity.supported_sample_rates == [stt.AudioSampleRates.SAMPLERATE_16000]
    assert entity.supported_channels == [stt.AudioChannels.CHANNEL_MONO]


async def test_streaming_audio(
    hass: HomeAssistant, init_wyoming_stt, metadata, snapshot: SnapshotAssertion
) -> None:
    """Test streaming audio."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream():
        yield "chunk1"
        yield "chunk2"

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([Transcript(text="Hello world").event()]),
    ) as mock_client:
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "Hello world"
    assert mock_client.written == snapshot


async def test_streaming_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_stt, metadata
) -> None:
    """Test streaming audio and losing connection."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream():
        yield "chunk1"

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


@pytest.mark.usefixtures("init_wyoming_stt")
@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        pytest.param(None, "Error from Wyoming service: Boom!", id="without_code"),
        pytest.param(
            "ModelNotFoundError",
            "Error from Wyoming service: Boom! (code: ModelNotFoundError)",
            id="with_code",
        ),
    ],
)
async def test_streaming_audio_error_event(
    hass: HomeAssistant,
    metadata: stt.SpeechMetadata,
    caplog: pytest.LogCaptureFixture,
    error_code: str | None,
    expected_message: str,
) -> None:
    """Test that an error event from the service is reported."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream():
        yield "chunk1"

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([Error(text="Boom!", code=error_code).event()]),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
    assert expected_message in caplog.text


async def test_streaming_audio_oserror(
    hass: HomeAssistant, init_wyoming_stt, metadata
) -> None:
    """Test streaming audio and error raising."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream():
        yield "chunk1"

    mock_client = MockAsyncTcpClient([Transcript(text="Hello world").event()])

    with (
        patch(
            "homeassistant.components.wyoming.stt.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "read_event", side_effect=OSError("Boom!")),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
