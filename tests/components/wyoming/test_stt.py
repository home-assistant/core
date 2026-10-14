"""Test stt."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.audio import AudioChunk, AudioStop
from wyoming.error import Error
from wyoming.event import Event

from homeassistant.components import stt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import STT_INFO, MockAsyncTcpClient


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_support(hass: HomeAssistant) -> None:
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
    assert entity.audio_processing == stt.SpeechAudioProcessing(
        requires_external_vad=True,
        prefers_auto_gain_enabled=True,
        prefers_noise_reduction_enabled=True,
    )


async def test_audio_processing(
    hass: HomeAssistant, stt_config_entry: ConfigEntry
) -> None:
    """Test advertised audio processing properties."""
    asr_program = replace(
        STT_INFO.asr[0],
        requires_external_vad=False,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=False,
    )
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=replace(STT_INFO, asr=[asr_program]),
    ):
        await hass.config_entries.async_setup(stt_config_entry.entry_id)

    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None
    assert entity.audio_processing == stt.SpeechAudioProcessing(
        requires_external_vad=False,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=False,
    )


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_streaming_audio(
    hass: HomeAssistant,
    metadata: stt.SpeechMetadata,
    snapshot: SnapshotAssertion,
) -> None:
    """Test streaming audio."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    class AudioStopTranscriptClient(MockAsyncTcpClient):
        async def write_event(self, event: Event) -> None:
            await super().write_event(event)
            if AudioStop.is_type(event.type):
                self.responses.append(Transcript(text="Hello world").event())

        async def read_event(self) -> Event | None:
            while not self.responses:
                await asyncio.sleep(0)
            return await super().read_event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        yield b"chunk1"
        yield b"chunk2"

    mock_client = AudioStopTranscriptClient([])
    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        mock_client,
    ) as mock_client:
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "Hello world"
    assert mock_client.written == snapshot


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_early_transcript_stops_audio_stream(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test an early transcript stops the source audio stream."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    audio_write_started = asyncio.Event()
    stream_closed = asyncio.Event()

    class EarlyTranscriptClient(MockAsyncTcpClient):
        async def write_event(self, event: Event) -> None:
            await super().write_event(event)
            if AudioChunk.is_type(event.type):
                audio_write_started.set()
                await asyncio.Event().wait()

        async def read_event(self) -> Event | None:
            await audio_write_started.wait()
            return await super().read_event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        try:
            yield b"chunk1"
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    mock_client = EarlyTranscriptClient([Transcript(text="Hello world").event()])
    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        mock_client,
    ):
        async with asyncio.timeout(1):
            result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "Hello world"
    assert stream_closed.is_set()
    assert any(AudioChunk.is_type(event.type) for event in mock_client.written)
    assert not any(AudioStop.is_type(event.type) for event in mock_client.written)


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_early_transcript_preserved_after_upload_error(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test an upload error does not replace a completed transcript."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream() -> AsyncGenerator[bytes]:
        yield b"chunk1"

    mock_client = MockAsyncTcpClient([Transcript(text="Hello world").event()])
    original_write_event = mock_client.write_event

    async def write_event(event: Event) -> None:
        await original_write_event(event)
        if AudioChunk.is_type(event.type):
            raise OSError("Connection closed")

    with (
        patch(
            "homeassistant.components.wyoming.stt.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "write_event", side_effect=write_event),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.SUCCESS
    assert result.text == "Hello world"


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_streaming_audio_connection_lost(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test streaming audio and losing connection."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    stream_closed = asyncio.Event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        try:
            yield b"chunk1"
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
    assert stream_closed.is_set()


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

    stream_closed = asyncio.Event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        try:
            yield b"chunk1"
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    with patch(
        "homeassistant.components.wyoming.stt.AsyncTcpClient",
        MockAsyncTcpClient([Error(text="Boom!", code=error_code).event()]),
    ):
        result = await entity.async_process_audio_stream(metadata, audio_stream())

    assert result.result == stt.SpeechResultState.ERROR
    assert result.text is None
    assert stream_closed.is_set()
    assert expected_message in caplog.text


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_streaming_audio_oserror(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test streaming audio and error raising."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    async def audio_stream() -> AsyncGenerator[bytes]:
        yield b"chunk1"

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


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_streaming_audio_source_error(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test an audio source error is propagated and stops receiving."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    receive_started = asyncio.Event()
    receive_cancelled = asyncio.Event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        yield b"chunk1"
        await receive_started.wait()
        raise RuntimeError("Boom!")

    async def read_event() -> None:
        try:
            receive_started.set()
            await asyncio.Event().wait()
        finally:
            receive_cancelled.set()

    mock_client = MockAsyncTcpClient([])
    with (
        patch(
            "homeassistant.components.wyoming.stt.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "read_event", side_effect=read_event),
        pytest.raises(RuntimeError, match="Boom!"),
    ):
        await entity.async_process_audio_stream(metadata, audio_stream())

    assert receive_cancelled.is_set()


@pytest.mark.usefixtures("init_wyoming_stt")
async def test_streaming_audio_cancellation(
    hass: HomeAssistant, metadata: stt.SpeechMetadata
) -> None:
    """Test cancellation stops both upload and receive tasks."""
    entity = stt.async_get_speech_to_text_entity(hass, "stt.test_asr")
    assert entity is not None

    audio_sent = asyncio.Event()
    stream_closed = asyncio.Event()
    receive_cancelled = asyncio.Event()

    async def audio_stream() -> AsyncGenerator[bytes]:
        try:
            yield b"chunk1"
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    mock_client = MockAsyncTcpClient([])
    original_write_event = mock_client.write_event

    async def write_event(event: Event) -> None:
        await original_write_event(event)
        if AudioChunk.is_type(event.type):
            audio_sent.set()

    async def read_event() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            receive_cancelled.set()

    with (
        patch(
            "homeassistant.components.wyoming.stt.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "write_event", side_effect=write_event),
        patch.object(mock_client, "read_event", side_effect=read_event),
    ):
        async with asyncio.timeout(1):
            process_task = asyncio.create_task(
                entity.async_process_audio_stream(metadata, audio_stream())
            )
            await audio_sent.wait()
            process_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await process_task

    assert stream_closed.is_set()
    assert receive_cancelled.is_set()
