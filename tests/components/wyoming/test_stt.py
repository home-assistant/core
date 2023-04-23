"""Test stt."""
from __future__ import annotations

from unittest.mock import patch

from wyoming.event import Event

from homeassistant.components import stt
from homeassistant.core import HomeAssistant


class MockAsyncTcpClient:
    """Mock AsyncTcpClient."""

    def __init__(self, responses) -> None:
        """Initialize."""
        self.host = None
        self.port = None
        self.written = []
        self.responses = responses

    async def write_event(self, event):
        """Send."""
        self.written.append(event)

    async def read_event(self):
        """Receive."""
        return self.responses.pop(0)

    async def __aenter__(self):
        """Enter."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit."""

    def __call__(self, host, port):
        """Call."""
        self.host = host
        self.port = port
        return self


async def test_support(hass: HomeAssistant, init_wyoming_stt) -> None:
    """Test streaming audio."""
    state = hass.states.get("stt.wyoming")
    assert state is not None

    entity = stt.async_get_speech_to_text_entity(hass, "stt.wyoming")

    assert entity.supported_languages == ["en-US"]
    assert entity.supported_formats == [stt.AudioFormats.WAV]
    assert entity.supported_codecs == [stt.AudioCodecs.PCM]
    assert entity.supported_bit_rates == [stt.AudioBitRates.BITRATE_16]
    assert entity.supported_sample_rates == [stt.AudioSampleRates.SAMPLERATE_16000]
    assert entity.supported_channels == [stt.AudioChannels.CHANNEL_MONO]


async def test_streaming_audio(hass: HomeAssistant, init_wyoming_stt, snapshot) -> None:
    """Test streaming audio."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.wyoming")

    async def audio_stream():
        yield "chunk1"
        yield "chunk2"

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([Event(type="transcript", data={"text": "Hello world"})]),
    ) as mock_client:
        result = await entity.async_process_audio_stream(None, audio_stream())

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "Hello world"
    assert mock_client.written == snapshot


async def test_streaming_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_stt
) -> None:
    """Test streaming audio and losing connection."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.wyoming")

    async def audio_stream():
        yield "chunk1"

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        result = await entity.async_process_audio_stream(None, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None


async def test_streaming_audio_oserror(hass: HomeAssistant, init_wyoming_stt) -> None:
    """Test streaming audio and error raising."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.wyoming")

    async def audio_stream():
        yield "chunk1"

    mock_client = MockAsyncTcpClient(
        [Event(type="transcript", data={"text": "Hello world"})]
    )

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        mock_client,
    ), patch.object(mock_client, "read_event", side_effect=OSError("Boom!")):
        result = await entity.async_process_audio_stream(None, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
