"""Test Wyoming satellite."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from wyoming.audio import AudioChunk
from wyoming.event import Event
from wyoming.pipeline import PipelineStage, RunPipeline
from wyoming.satellite import RunSatellite
from wyoming.vad import VoiceStarted, VoiceStopped
from wyoming.wake import Detect, Detection

from homeassistant.components import assist_pipeline, wyoming
from homeassistant.components.wyoming.devices import SatelliteDevices
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import SATELLITE_INFO, MockAsyncTcpClient

from tests.common import MockConfigEntry


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

        self.stt_vad_start_event = asyncio.Event()
        self.voice_started: VoiceStarted | None = None

        self.stt_vad_end_event = asyncio.Event()
        self.voice_stopped: VoiceStopped | None = None

        self._audio_chunk = AudioChunk(
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
            self.detection_event.set()
            self.detection = Detection.from_event(event)
        elif VoiceStarted.is_type(event.type):
            self.stt_vad_start_event.set()
            self.voice_started = VoiceStarted.from_event(event)
        elif VoiceStopped.is_type(event.type):
            self.stt_vad_end_event.set()
            self.voice_stopped = VoiceStopped.from_event(event)

    async def read_event(self) -> Event | None:
        """Receive."""
        event = await super().read_event()

        # Keep sending audio chunks
        return event or self._audio_chunk


async def test_satellite(hass: HomeAssistant) -> None:
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
    ) as mock_run_pipeline:
        entry = MockConfigEntry(
            domain="wyoming",
            data={
                "host": "1.2.3.4",
                "port": 1234,
            },
            title="Test Satellite",
            unique_id="1234_test",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        satellite_devices: SatelliteDevices = hass.data[wyoming.DOMAIN][
            entry.entry_id
        ].satellite_devices
        assert entry.entry_id in satellite_devices.devices
        device = satellite_devices.devices[entry.entry_id]

        async with asyncio.timeout(1):
            await mock_client.connect_event.wait()
            await mock_client.run_satellite_event.wait()

        mock_run_pipeline.assert_called()
        event_callback = mock_run_pipeline.call_args.kwargs["event_callback"]

        # Start detecting wake word
        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.WAKE_WORD_START
            )
        )
        async with asyncio.timeout(1):
            await mock_client.detect_event.wait()

        assert not device.is_active
        assert device.is_enabled

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

        # Speech to text started
        event_callback(
            assist_pipeline.PipelineEvent(assist_pipeline.PipelineEventType.STT_START)
        )

        event_callback(
            assist_pipeline.PipelineEvent(
                assist_pipeline.PipelineEventType.STT_VAD_START, {"timestamp": 1234}
            )
        )
        async with asyncio.timeout(1):
            await mock_client.stt_vad_start_event.wait()

        assert mock_client.voice_started is not None
        assert mock_client.voice_started.timestamp == 1234

        # Pipeline finished
        event_callback(
            assist_pipeline.PipelineEvent(assist_pipeline.PipelineEventType.RUN_END)
        )
        assert not device.is_active

        # Stop the satellite
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
