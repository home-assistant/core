"""Test Wyoming satellite."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import io
from typing import Any
from unittest.mock import patch
import wave

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Info
from wyoming.ping import Ping, Pong
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite
from wyoming.timer import TimerCancelled, TimerFinished, TimerStarted, TimerUpdated
from wyoming.tts import Synthesize
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, wyoming
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import intent as intent_helper
from homeassistant.setup import async_setup_component

from . import SATELLITE_INFO, WAKE_WORD_INFO, MockAsyncTcpClient

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

        self.pong_event = asyncio.Event()
        self.pong: Pong | None = None

        self.ping_event = asyncio.Event()
        self.ping: Ping | None = None

        self.timer_started_event = asyncio.Event()
        self.timer_started: TimerStarted | None = None

        self.timer_updated_event = asyncio.Event()
        self.timer_updated: TimerUpdated | None = None

        self.timer_cancelled_event = asyncio.Event()
        self.timer_cancelled: TimerCancelled | None = None

        self.timer_finished_event = asyncio.Event()
        self.timer_finished: TimerFinished | None = None

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
        elif Pong.is_type(event.type):
            self.pong = Pong.from_event(event)
            self.pong_event.set()
        elif Ping.is_type(event.type):
            self.ping = Ping.from_event(event)
            self.ping_event.set()
        elif TimerStarted.is_type(event.type):
            self.timer_started = TimerStarted.from_event(event)
            self.timer_started_event.set()
        elif TimerUpdated.is_type(event.type):
            self.timer_updated = TimerUpdated.from_event(event)
            self.timer_updated_event.set()
        elif TimerCancelled.is_type(event.type):
            self.timer_cancelled = TimerCancelled.from_event(event)
            self.timer_cancelled_event.set()
        elif TimerFinished.is_type(event.type):
            self.timer_finished = TimerFinished.from_event(event)
            self.timer_finished_event.set()

    async def read_event(self) -> Event | None:
        """Receive."""
        event = await super().read_event()

        # Keep sending audio chunks instead of None
        return event or self._mic_audio_chunk

    def inject_event(self, event: Event) -> None:
        """Put an event in as the next response."""
        self.responses = [event, *self.responses]


async def test_satellite_pipeline(hass: HomeAssistant) -> None:
    """Test running a pipeline with a satellite."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE,
            end_stage=PipelineStage.TTS,
            restart_on_end=True,
        ).event(),
    ]

    pipeline_kwargs: dict[str, Any] = {}
    pipeline_event_callback: Callable[[assist_pipeline.PipelineEvent], None] | None = (
        None
    )
    run_pipeline_called = asyncio.Event()
    audio_chunk_received = asyncio.Event()

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context,
        event_callback,
        stt_metadata,
        stt_stream,
        **kwargs,
    ) -> None:
        nonlocal pipeline_kwargs, pipeline_event_callback
        pipeline_kwargs = kwargs
        pipeline_event_callback = event_callback

        run_pipeline_called.set()
        async for chunk in stt_stream:
            if chunk:
                audio_chunk_received.set()
                break

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            async_pipeline_from_audio_stream,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.tts.async_get_media_source_audio",
            return_value=("wav", get_test_wav()),
        ),
        patch("homeassistant.components.wyoming.satellite._PING_SEND_DELAY", 0),
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        async with asyncio.timeout(1):
            await run_pipeline_called.wait()

            # Reset so we can check the pipeline is automatically restarted below
            run_pipeline_called.clear()

        assert pipeline_event_callback is not None
        assert pipeline_kwargs.get("device_id") == device.device_id

        # Test a ping
        mock_client.inject_event(Ping("test-ping").event())

        # Pong is expected with the same text
        async with asyncio.timeout(1):
            await mock_client.pong_event.wait()

        assert mock_client.pong is not None
        assert mock_client.pong.text == "test-ping"

        # The client should have received the first ping
        async with asyncio.timeout(1):
            await mock_client.ping_event.wait()

        assert mock_client.ping is not None

        # Reset and send a pong back.
        # We will get a second ping by the end of the test.
        mock_client.ping_event.clear()
        mock_client.ping = None
        mock_client.inject_event(Pong().event())

        # Start detecting wake word
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.WAKE_WORD_START
            )
        )
        async with asyncio.timeout(1):
            await mock_client.detect_event.wait()

        assert not device.is_active
        assert not device.is_muted

        # Push in some audio
        mock_client.inject_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=bytes(1024)).event()
        )

        # Wake word is detected
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.WAKE_WORD_END,
                {"wake_word_output": {"wake_word_id": "test_wake_word"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.detection_event.wait()

        assert mock_client.detection is not None
        assert mock_client.detection.name == "test_wake_word"

        # Speech-to-text started
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_START,
                {"metadata": {"language": "en"}},
            )
        )
        async with asyncio.timeout(1):
            await mock_client.transcribe_event.wait()

        assert mock_client.transcribe is not None
        assert mock_client.transcribe.language == "en"

        # "Assist in progress" sensor should be active now
        assert device.is_active

        # Push in some audio
        mock_client.inject_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=bytes(1024)).event()
        )

        # User started speaking
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_VAD_START, {"timestamp": 1234}
            )
        )
        async with asyncio.timeout(1):
            await mock_client.voice_started_event.wait()

        assert mock_client.voice_started is not None
        assert mock_client.voice_started.timestamp == 1234

        # User stopped speaking
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_VAD_END, {"timestamp": 5678}
            )
        )
        async with asyncio.timeout(1):
            await mock_client.voice_stopped_event.wait()

        assert mock_client.voice_stopped is not None
        assert mock_client.voice_stopped.timestamp == 5678

        # Speech-to-text transcription
        pipeline_event_callback(
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
        pipeline_event_callback(
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
        pipeline_event_callback(
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
        pipeline_event_callback(
            assist_pipeline.PipelineEvent(assist_pipeline.PipelineEventType.RUN_END)
        )
        assert not device.is_active

        # The client should have received another ping by now
        async with asyncio.timeout(1):
            await mock_client.ping_event.wait()

        assert mock_client.ping is not None

        # Pipeline should automatically restart
        async with asyncio.timeout(1):
            await run_pipeline_called.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_satellite_muted(hass: HomeAssistant) -> None:
    """Test callback for a satellite that has been muted."""
    on_muted_event = asyncio.Event()

    original_on_muted = wyoming.satellite.WyomingSatellite.on_muted

    async def on_muted(self):
        # Trigger original function
        self._muted_changed_event.set()
        await original_on_muted(self)

        # Ensure satellite stops
        self.is_running = False

        # Proceed with test
        self.device.set_is_muted(False)
        on_muted_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.switch.WyomingSatelliteMuteSwitch.async_get_last_state",
            return_value=State("switch.test_mute", STATE_ON),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_muted",
            on_muted,
        ),
    ):
        entry = await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await on_muted_event.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_satellite_restart(hass: HomeAssistant) -> None:
    """Test pipeline loop restart after unexpected error."""
    on_restart_event = asyncio.Event()

    original_on_restart = wyoming.satellite.WyomingSatellite.on_restart

    async def on_restart(self):
        await original_on_restart(self)
        self.stop()
        on_restart_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite._connect_and_loop",
            side_effect=RuntimeError(),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
            on_restart,
        ),
        patch("homeassistant.components.wyoming.satellite._RESTART_SECONDS", 0),
    ):
        await setup_config_entry(hass)
        async with asyncio.timeout(1):
            await on_restart_event.wait()


async def test_satellite_reconnect(hass: HomeAssistant) -> None:
    """Test satellite reconnect call after connection refused."""
    num_reconnects = 0
    reconnect_event = asyncio.Event()
    stopped_event = asyncio.Event()

    original_on_reconnect = wyoming.satellite.WyomingSatellite.on_reconnect

    async def on_reconnect(self):
        await original_on_reconnect(self)

        nonlocal num_reconnects
        num_reconnects += 1
        if num_reconnects >= 2:
            reconnect_event.set()
            self.stop()

    async def on_stopped(self):
        stopped_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient.connect",
            side_effect=ConnectionRefusedError(),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_reconnect",
            on_reconnect,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_stopped",
            on_stopped,
        ),
        patch("homeassistant.components.wyoming.satellite._RECONNECT_SECONDS", 0),
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

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            MockAsyncTcpClient([]),  # no RunPipeline event
        ),
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
        ) as mock_run_pipeline,
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
            on_restart,
        ),
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

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            MockAsyncTcpClient(events),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
        ) as mock_run_pipeline,
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_restart",
            on_restart,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite.on_stopped",
            on_stopped,
        ),
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

    pipeline_event = asyncio.Event()

    def _async_pipeline_from_audio_stream(*args: Any, **kwargs: Any) -> None:
        pipeline_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            wraps=_async_pipeline_from_audio_stream,
        ) as mock_run_pipeline,
    ):
        await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await pipeline_event.wait()
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


async def test_tts_not_wav(hass: HomeAssistant) -> None:
    """Test satellite receiving non-WAV audio from text-to-speech."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    original_stream_tts = wyoming.satellite.WyomingSatellite._stream_tts
    error_event = asyncio.Event()

    async def _stream_tts(self, media_id):
        try:
            await original_stream_tts(self, media_id)
        except ValueError:
            error_event.set()

    events = [
        RunPipeline(start_stage=PipelineStage.TTS, end_stage=PipelineStage.TTS).event(),
    ]
    pipeline_event = asyncio.Event()

    def _async_pipeline_from_audio_stream(*args: Any, **kwargs: Any) -> None:
        pipeline_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            wraps=_async_pipeline_from_audio_stream,
        ) as mock_run_pipeline,
        patch(
            "homeassistant.components.wyoming.satellite.tts.async_get_media_source_audio",
            return_value=("mp3", bytes(1)),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite._stream_tts",
            _stream_tts,
        ),
    ):
        entry = await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await pipeline_event.wait()
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        mock_run_pipeline.assert_called_once()
        event_callback = mock_run_pipeline.call_args.kwargs["event_callback"]

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

        # Text-to-speech media
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.TTS_END,
                {"tts_output": {"media_id": "test media id"}},
            )
        )

        # Expect error because only WAV is supported
        async with asyncio.timeout(1):
            await error_event.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_pipeline_changed(hass: HomeAssistant) -> None:
    """Test that changing the pipeline setting stops the current pipeline."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    pipeline_event_callback: Callable[[assist_pipeline.PipelineEvent], None] | None = (
        None
    )
    run_pipeline_called = asyncio.Event()
    pipeline_stopped = asyncio.Event()

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context,
        event_callback,
        stt_metadata,
        stt_stream,
        **kwargs,
    ) -> None:
        nonlocal pipeline_event_callback
        pipeline_event_callback = event_callback

        run_pipeline_called.set()
        async for _chunk in stt_stream:
            pass

        pipeline_stopped.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            async_pipeline_from_audio_stream,
        ),
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        # Pipeline has started
        async with asyncio.timeout(1):
            await run_pipeline_called.wait()

        assert pipeline_event_callback is not None

        # Change pipelines
        device.set_pipeline_name("different pipeline")

        # Running pipeline should be cancelled
        async with asyncio.timeout(1):
            await pipeline_stopped.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_audio_settings_changed(hass: HomeAssistant) -> None:
    """Test that changing audio settings stops the current pipeline."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    pipeline_event_callback: Callable[[assist_pipeline.PipelineEvent], None] | None = (
        None
    )
    run_pipeline_called = asyncio.Event()
    pipeline_stopped = asyncio.Event()

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context,
        event_callback,
        stt_metadata,
        stt_stream,
        **kwargs,
    ) -> None:
        nonlocal pipeline_event_callback
        pipeline_event_callback = event_callback

        run_pipeline_called.set()
        async for _chunk in stt_stream:
            pass

        pipeline_stopped.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            async_pipeline_from_audio_stream,
        ),
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        # Pipeline has started
        async with asyncio.timeout(1):
            await run_pipeline_called.wait()

        assert pipeline_event_callback is not None

        # Change audio setting
        device.set_noise_suppression_level(1)

        # Running pipeline should be cancelled
        async with asyncio.timeout(1):
            await pipeline_stopped.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_invalid_stages(hass: HomeAssistant) -> None:
    """Test error when providing invalid pipeline stages."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    original_run_pipeline_once = wyoming.satellite.WyomingSatellite._run_pipeline_once
    start_stage_event = asyncio.Event()
    end_stage_event = asyncio.Event()

    def _run_pipeline_once(self, run_pipeline, wake_word_phrase):
        # Set bad start stage
        run_pipeline.start_stage = PipelineStage.INTENT
        run_pipeline.end_stage = PipelineStage.TTS

        try:
            original_run_pipeline_once(self, run_pipeline)
        except ValueError:
            start_stage_event.set()

        # Set bad end stage
        run_pipeline.start_stage = PipelineStage.WAKE
        run_pipeline.end_stage = PipelineStage.INTENT

        try:
            original_run_pipeline_once(self, run_pipeline)
        except ValueError:
            end_stage_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.WyomingSatellite._run_pipeline_once",
            _run_pipeline_once,
        ),
    ):
        entry = await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        async with asyncio.timeout(1):
            await start_stage_event.wait()
            await end_stage_event.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_client_stops_pipeline(hass: HomeAssistant) -> None:
    """Test that an AudioStop message stops the current pipeline."""
    assert await async_setup_component(hass, assist_pipeline.DOMAIN, {})

    events = [
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    pipeline_event_callback: Callable[[assist_pipeline.PipelineEvent], None] | None = (
        None
    )
    run_pipeline_called = asyncio.Event()
    pipeline_stopped = asyncio.Event()

    async def async_pipeline_from_audio_stream(
        hass: HomeAssistant,
        context,
        event_callback,
        stt_metadata,
        stt_stream,
        **kwargs,
    ) -> None:
        nonlocal pipeline_event_callback
        pipeline_event_callback = event_callback

        run_pipeline_called.set()
        async for _chunk in stt_stream:
            pass

        pipeline_stopped.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ) as mock_client,
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            async_pipeline_from_audio_stream,
        ),
    ):
        entry = await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        # Pipeline has started
        async with asyncio.timeout(1):
            await run_pipeline_called.wait()

        assert pipeline_event_callback is not None

        # Client sends stop message
        mock_client.inject_event(AudioStop().event())

        # Running pipeline should be cancelled
        async with asyncio.timeout(1):
            await pipeline_stopped.wait()

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_wake_word_phrase(hass: HomeAssistant) -> None:
    """Test that wake word phrase from info is given to pipeline."""
    events = [
        # Fake local wake word detection
        Info(satellite=SATELLITE_INFO.satellite, wake=WAKE_WORD_INFO.wake).event(),
        Detection(name="Test Model").event(),
        RunPipeline(
            start_stage=PipelineStage.WAKE, end_stage=PipelineStage.TTS
        ).event(),
    ]

    pipeline_event = asyncio.Event()

    def _async_pipeline_from_audio_stream(*args: Any, **kwargs: Any) -> None:
        pipeline_event.set()

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient(events),
        ),
        patch(
            "homeassistant.components.wyoming.satellite.assist_pipeline.async_pipeline_from_audio_stream",
            wraps=_async_pipeline_from_audio_stream,
        ) as mock_run_pipeline,
    ):
        await setup_config_entry(hass)

        async with asyncio.timeout(1):
            await pipeline_event.wait()

        # async_pipeline_from_audio_stream will receive the wake word phrase for
        # deconfliction.
        mock_run_pipeline.assert_called_once()
        assert (
            mock_run_pipeline.call_args.kwargs.get("wake_word_phrase") == "Test Phrase"
        )


async def test_timers(hass: HomeAssistant) -> None:
    """Test timer events."""
    assert await async_setup_component(hass, "intent", {})

    with (
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=SATELLITE_INFO,
        ),
        patch(
            "homeassistant.components.wyoming.satellite.AsyncTcpClient",
            SatelliteAsyncTcpClient([]),
        ) as mock_client,
    ):
        entry = await setup_config_entry(hass)
        device: SatelliteDevice = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite.device

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        # Start timer
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_START_TIMER,
            {
                "name": {"value": "test timer"},
                "hours": {"value": 1},
                "minutes": {"value": 2},
                "seconds": {"value": 3},
            },
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_started_event.wait()
            timer_started = mock_client.timer_started
            assert timer_started is not None
            assert timer_started.id
            assert timer_started.name == "test timer"
            assert timer_started.start_hours == 1
            assert timer_started.start_minutes == 2
            assert timer_started.start_seconds == 3
            assert timer_started.total_seconds == (1 * 60 * 60) + (2 * 60) + 3

        # Pause
        mock_client.timer_updated_event.clear()
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_PAUSE_TIMER,
            {},
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_updated_event.wait()
            timer_updated = mock_client.timer_updated
            assert timer_updated is not None
            assert timer_updated.id == timer_started.id
            assert not timer_updated.is_active

        # Resume
        mock_client.timer_updated_event.clear()
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_UNPAUSE_TIMER,
            {},
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_updated_event.wait()
            timer_updated = mock_client.timer_updated
            assert timer_updated is not None
            assert timer_updated.id == timer_started.id
            assert timer_updated.is_active

        # Add time
        mock_client.timer_updated_event.clear()
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_INCREASE_TIMER,
            {
                "hours": {"value": 2},
                "minutes": {"value": 3},
                "seconds": {"value": 4},
            },
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_updated_event.wait()
            timer_updated = mock_client.timer_updated
            assert timer_updated is not None
            assert timer_updated.id == timer_started.id
            assert timer_updated.total_seconds > timer_started.total_seconds

        # Remove time
        mock_client.timer_updated_event.clear()
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_DECREASE_TIMER,
            {
                "hours": {"value": 2},
                "minutes": {"value": 3},
                "seconds": {"value": 5},  # remove 1 extra second
            },
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_updated_event.wait()
            timer_updated = mock_client.timer_updated
            assert timer_updated is not None
            assert timer_updated.id == timer_started.id
            assert timer_updated.total_seconds < timer_started.total_seconds

        # Cancel
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_CANCEL_TIMER,
            {},
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_cancelled_event.wait()
            timer_cancelled = mock_client.timer_cancelled
            assert timer_cancelled is not None
            assert timer_cancelled.id == timer_started.id

        # Start a new timer
        mock_client.timer_started_event.clear()
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_START_TIMER,
            {
                "name": {"value": "test timer"},
                "minutes": {"value": 1},
            },
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_started_event.wait()
            timer_started = mock_client.timer_started
            assert timer_started is not None

        # Finished
        result = await intent_helper.async_handle(
            hass,
            "test",
            intent_helper.INTENT_DECREASE_TIMER,
            {
                "minutes": {"value": 1},  # force finish
            },
            device_id=device.device_id,
        )

        assert result.response_type == intent_helper.IntentResponseType.ACTION_DONE
        async with asyncio.timeout(1):
            await mock_client.timer_finished_event.wait()
            timer_finished = mock_client.timer_finished
            assert timer_finished is not None
            assert timer_finished.id == timer_started.id
