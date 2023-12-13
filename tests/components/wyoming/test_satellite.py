"""Test Wyoming satellite."""
from __future__ import annotations

import asyncio
import io
from unittest.mock import patch
import wave

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite
from wyoming.tts import Synthesize
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, wyoming
from homeassistant.components.wyoming.data import WyomingService
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import SATELLITE_INFO, MockAsyncTcpClient

from tests.common import MockConfigEntry


async def setup_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up config entry for Wyoming satellite.

    This is separated from the satellite_config_entry method in conftest.py so
    we can patch functions before the satellite task is run during setup.
    """
    entry = MockConfigEntry(
        domain="wyoming",
        data={
            "host": "1.2.3.4",
            "port": 1234,
        },
        title="Test Satellite",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def get_test_wav() -> bytes:
    """Get bytes for test WAV file."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(22050)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)

            # Single frame
            wav_file.writeframes(b"123")

        return wav_io.getvalue()


class SatelliteAsyncTcpClient(MockAsyncTcpClient):
    """Satellite AsyncTcpClient."""

    def __init__(self, responses: list[Event]) -> None:
        """Initialize client."""
        super().__init__(responses)

        self.connect_event = asyncio.Event()
        self.run_satellite_event = asyncio.Event()
        self.detect_event = asyncio.Event()

        self.detection_event = asyncio.Event()
        self.detection: Detection | None = None

        self.transcribe_event = asyncio.Event()
        self.transcribe: Transcribe | None = None

        self.voice_started_event = asyncio.Event()
        self.voice_started: VoiceStarted | None = None

        self.voice_stopped_event = asyncio.Event()
        self.voice_stopped: VoiceStopped | None = None

        self.transcript_event = asyncio.Event()
        self.transcript: Transcript | None = None

        self.synthesize_event = asyncio.Event()
        self.synthesize: Synthesize | None = None

        self.tts_audio_start_event = asyncio.Event()
        self.tts_audio_chunk_event = asyncio.Event()
        self.tts_audio_stop_event = asyncio.Event()
        self.tts_audio_chunk: AudioChunk | None = None

        self.error_event = asyncio.Event()
        self.error: Error | None = None

        self._mic_audio_chunk = AudioChunk(
            rate=16000, width=2, channels=1, audio=b"chunk"
        ).event()

    async def connect(self) -> None:
        """Connect."""
        self.connect_event.set()

    async def write_event(self, event: Event):
        """Send."""
        if RunSatellite.is_type(event.type):
            self.run_satellite_event.set()
        elif Detect.is_type(event.type):
            self.detect_event.set()
        elif Detection.is_type(event.type):
            self.detection = Detection.from_event(event)
            self.detection_event.set()
        elif Transcribe.is_type(event.type):
            self.transcribe = Transcribe.from_event(event)
            self.transcribe_event.set()
        elif VoiceStarted.is_type(event.type):
            self.voice_started = VoiceStarted.from_event(event)
            self.voice_started_event.set()
        elif VoiceStopped.is_type(event.type):
            self.voice_stopped = VoiceStopped.from_event(event)
            self.voice_stopped_event.set()
        elif Transcript.is_type(event.type):
            self.transcript = Transcript.from_event(event)
            self.transcript_event.set()
        elif Synthesize.is_type(event.type):
            self.synthesize = Synthesize.from_event(event)
            self.synthesize_event.set()
        elif AudioStart.is_type(event.type):
            self.tts_audio_start_event.set()
        elif AudioChunk.is_type(event.type):
            self.tts_audio_chunk = AudioChunk.from_event(event)
            self.tts_audio_chunk_event.set()
        elif AudioStop.is_type(event.type):
            self.tts_audio_stop_event.set()
        elif Error.is_type(event.type):
            self.error = Error.from_event(event)
            self.error_event.set()

    async def read_event(self) -> Event | None:
        """Receive."""
        event = await super().read_event()

        # Keep sending audio chunks instead of None
        return event or self._mic_audio_chunk


async def test_satellite_pipeline(hass: HomeAssistant) -> None:
    """Test running a pipeline with a satellite."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.AsyncTcpClient",
        SatelliteAsyncTcpClient(events),
    ) as mock_client, patch(
        "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
    ) as mock_run_pipeline, patch(
        "homeassistant.components.wyoming.satellite.tts.async_get_media_source_audio",
        return_value=("wav", get_test_wav()),
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        mock_run_pipeline.assert_called_once()
        event_callback = mock_run_pipeline.call_args.kwargs["event_callback"]
        assert mock_run_pipeline.call_args.kwargs.get("device_id") == device.device_id

        # Start detecting wake word
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.WAKE_WORD_START
            )
        )
        async with asyncio.timeout(1):
            await mock_client.detect_event.wait()

        assert not device.is_active
        assert not device.is_muted

        # Wake word is detected
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.WAKE_WORD_END,
                {"wake_word_output": {"wake_word_id": "test_wake_word"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.detection_event.wait()

        assert mock_client.detection is not None
        assert mock_client.detection.name == "test_wake_word"

        # "Assist in progress" sensor should be active now
        assert device.is_active

        # Speech-to-text started
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_START,
                {"metadata": {"language": "en"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.transcribe_event.wait()

        assert mock_client.transcribe is not None
        assert mock_client.transcribe.language == "en"

        # User started speaking
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_VAD_START, {"timestamp": 1234}
            )
        )
        async with asyncio.timeout(1):
            await mock_client.voice_started_event.wait()

        assert mock_client.voice_started is not None
        assert mock_client.voice_started.timestamp == 1234

        # User stopped speaking
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_VAD_END, {"timestamp": 5678}
            )
        )
        async with asyncio.timeout(1):
            await mock_client.voice_stopped_event.wait()

        assert mock_client.voice_stopped is not None
        assert mock_client.voice_stopped.timestamp == 5678

        # Speech-to-text transcription
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_END,
                {"stt_output": {"text": "test transcript"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.transcript_event.wait()

        assert mock_client.transcript is not None
        assert mock_client.transcript.text == "test transcript"

        # Text-to-speech text
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.TTS_START,
                {
                    "tts_input": "test text to speak",
                    "voice": "test voice",
                },
            )
        )
        async with asyncio.timeout(1):
            await mock_client.synthesize_event.wait()

        assert mock_client.synthesize is not None
        assert mock_client.synthesize.text == "test text to speak"
        assert mock_client.synthesize.voice is not None
        assert mock_client.synthesize.voice.name == "test voice"

        # Text-to-speech media
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.TTS_END,
                {"tts_output": {"media_id": "test media id"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.tts_audio_start_event.wait()
            await mock_client.tts_audio_chunk_event.wait()
            await mock_client.tts_audio_stop_event.wait()

        # Verify audio chunk from test WAV
        assert mock_client.tts_audio_chunk is not None
        assert mock_client.tts_audio_chunk.rate == 22050
        assert mock_client.tts_audio_chunk.width == 2
        assert mock_client.tts_audio_chunk.channels == 1
        assert mock_client.tts_audio_chunk.audio == b"123"

        # Pipeline finished
        event_callback(
            assist_pipeline.PipelineEvent(assist_pipeline.PipelineEventType.RUN_END)
        )
        assert not device.is_active

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_satellite_muted(hass: HomeAssistant) -> None:
    """Test callback for a satellite that has been muted."""
    on_muted_event = asyncio.Event()

    original_make_satellite = wyoming._make_satellite

    def make_muted_satellite(
        hass: HomeAssistant, config_entry: ConfigEntry, service: WyomingService
    ):
        satellite = original_make_satellite(hass, config_entry, service)
        satellite.device.set_is_muted(True)

        return satellite

    async def on_muted(self):
        self.device.set_is_muted(False)
        on_muted_event.set()

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming._make_satellite", make_muted_satellite
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_muted",
        on_muted,
    ):
        await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await on_muted_event.wait()


async def test_satellite_restart(hass: HomeAssistant) -> None:
    """Test pipeline loop restart after unexpected error."""
    on_restart_event = asyncio.Event()

    async def on_restart(self):
        self.stop()
        on_restart_event.set()

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite._run_once",
        side_effect=RuntimeError(),
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
        on_restart,
    ):
        await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await on_restart_event.wait()


async def test_satellite_reconnect(hass: HomeAssistant) -> None:
    """Test satellite reconnect call after connection refused."""
    num_reconnects = 0
    reconnect_event = asyncio.Event()
    stopped_event = asyncio.Event()

    async def on_reconnect(self):
        nonlocal num_reconnects
        num_reconnects += 1
        if num_reconnects >= 2:
            reconnect_event.set()
            self.stop()

    async def on_stopped(self):
        stopped_event.set()

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.AsyncTcpClient.connect",
        side_effect=ConnectionRefusedError(),
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_reconnect",
        on_reconnect,
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_stopped",
        on_stopped,
    ):
        await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await reconnect_event.wait()
            await stopped_event.wait()


async def test_satellite_disconnect_before_pipeline(hass: HomeAssistant) -> None:
    """Test satellite disconnecting before pipeline run."""
    on_restart_event = asyncio.Event()

    async def on_restart(self):
        self.stop()
        on_restart_event.set()

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.AsyncTcpClient",
        MockAsyncTcpClient([]),  # no RunPipeline event
    ), patch(
        "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
    ) as mock_run_pipeline, patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
        on_restart,
    ):
        await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await on_restart_event.wait()

        # Pipeline should never have run
        mock_run_pipeline.assert_not_called()


async def test_satellite_disconnect_during_pipeline(hass: HomeAssistant) -> None:
    """Test satellite disconnecting during pipeline run."""
    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]  # no audio chunks after RunPipeline

    on_restart_event = asyncio.Event()
    on_stopped_event = asyncio.Event()

    async def on_restart(self):
        # Pretend sensor got stuck on
        self.device.is_active = True
        self.stop()
        on_restart_event.set()

    async def on_stopped(self):
        on_stopped_event.set()

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.AsyncTcpClient",
        MockAsyncTcpClient(events),
    ), patch(
        "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
    ) as mock_run_pipeline, patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
        on_restart,
    ), patch(
        "homeassistant.components.wyoming.satellite.WyomingSatellite.on_stopped",
        on_stopped,
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await on_restart_event.wait()
            await on_stopped_event.wait()

        # Pipeline should have run once
        mock_run_pipeline.assert_called_once()

        # Sensor should have been turned off
        assert not device.is_active


async def test_satellite_error_during_pipeline(hass: HomeAssistant) -> None:
    """Test satellite error occurring during pipeline run."""
    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]  # no audio chunks after RunPipeline

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=SATELLITE_INFO,
    ), patch(
        "homeassistant.components.wyoming.satellite.AsyncTcpClient",
        SatelliteAsyncTcpClient(events),
    ) as mock_client, patch(
        "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
    ) as mock_run_pipeline:
        await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        mock_run_pipeline.assert_called_once()
        event_callback = mock_run_pipeline.call_args.kwargs["event_callback"]
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.ERROR,
                {"code": "test code", "message": "test message"},
            )
        )

        async with asyncio.timeout(1):
            await mock_client.error_event.wait()

        assert mock_client.error is not None
        assert mock_client.error.text == "test message"
        assert mock_client.error.code == "test code"
