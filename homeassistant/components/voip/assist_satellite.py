"""Assist satellite entity for VoIP integration."""

from __future__ import annotations

import asyncio
from enum import IntFlag
from functools import partial
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final
import wave

from voip_utils import RtpDatagramProtocol

from homeassistant.components import tts
from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventType,
    PipelineNotFound,
)
from homeassistant.components.assist_satellite import (
    AssistSatelliteEntity,
    AssistSatelliteEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.async_ import queue_to_iterable

from .const import CHANNELS, DOMAIN, RATE, RTP_AUDIO_SETTINGS, WIDTH
from .devices import VoIPDevice
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData

_LOGGER = logging.getLogger(__name__)

_PIPELINE_TIMEOUT_SEC: Final = 30


class Tones(IntFlag):
    """Feedback tones for specific events."""

    LISTENING = 1
    PROCESSING = 2
    ERROR = 4


_TONE_FILENAMES: dict[Tones, str] = {
    Tones.LISTENING: "tone.pcm",
    Tones.PROCESSING: "processing.pcm",
    Tones.ERROR: "error.pcm",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP Assist satellite entity."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoipAssistSatellite(hass, device, config_entry)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    entities: list[VoIPEntity] = [
        VoipAssistSatellite(hass, device, config_entry)
        for device in domain_data.devices
    ]

    async_add_entities(entities)


class VoipAssistSatellite(VoIPEntity, AssistSatelliteEntity, RtpDatagramProtocol):
    """Assist satellite for VoIP devices."""

    entity_description = AssistSatelliteEntityDescription(key="assist_satellite")
    _attr_translation_key = "assist_satellite"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        voip_device: VoIPDevice,
        config_entry: ConfigEntry,
        tones=Tones.LISTENING | Tones.PROCESSING | Tones.ERROR,
    ) -> None:
        """Initialize an Assist satellite."""
        VoIPEntity.__init__(self, voip_device)
        AssistSatelliteEntity.__init__(self)
        RtpDatagramProtocol.__init__(self)

        self.config_entry = config_entry

        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._audio_chunk_timeout: float = 2.0
        self._pipeline_task: asyncio.Task | None = None
        self._pipeline_had_error: bool = False
        self._tts_done = asyncio.Event()
        self._tts_extra_timeout: float = 1.0
        self._tone_bytes: dict[Tones, bytes] = {}
        self._tones = tones
        self._processing_tone_done = asyncio.Event()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.voip_device.protocol = self

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        assert self.voip_device.protocol == self
        self.voip_device.protocol = None

    # -------------------------------------------------------------------------
    # VoIP
    # -------------------------------------------------------------------------

    def on_chunk(self, audio_bytes: bytes) -> None:
        """Handle raw audio chunk."""
        if self._pipeline_task is None:
            self._clear_audio_queue()

            # Run pipeline until voice command finishes, then start over
            self._pipeline_task = self.config_entry.async_create_background_task(
                self.hass,
                self._run_pipeline(),
                "voip_pipeline_run",
            )

        self._audio_queue.put_nowait(audio_bytes)

    async def _run_pipeline(
        self,
    ) -> None:
        """Forward audio to pipeline STT and handle TTS."""
        self.async_set_context(Context(user_id=self.config_entry.data["user"]))
        self.voip_device.set_is_active(True)

        # Play listening tone at the start of each cycle
        await self._play_tone(Tones.LISTENING, silence_before=0.2)

        try:
            self._tts_done.clear()

            # Run pipeline with a timeout
            _LOGGER.debug("Starting pipeline")
            async with asyncio.timeout(_PIPELINE_TIMEOUT_SEC):
                await self._async_accept_pipeline_from_satellite(  # noqa: SLF001
                    audio_stream=queue_to_iterable(
                        self._audio_queue, timeout=self._audio_chunk_timeout
                    ),
                    pipeline_entity_id=self.voip_device.get_pipeline_entity_id(
                        self.hass
                    ),
                    vad_sensitivity_entity_id=self.voip_device.get_vad_sensitivity_entity_id(
                        self.hass
                    ),
                )

            if self._pipeline_had_error:
                self._pipeline_had_error = False
                await self._play_tone(Tones.ERROR)
            else:
                # Block until TTS is done speaking.
                #
                # This is set in _send_tts and has a timeout that's based on the
                # length of the TTS audio.
                await self._tts_done.wait()

            _LOGGER.debug("Pipeline finished")
        except PipelineNotFound:
            _LOGGER.warning("Pipeline not found")
        except (asyncio.CancelledError, TimeoutError):
            # Expected after caller hangs up
            _LOGGER.debug("Pipeline cancelled or timed out")
            self.disconnect()
            self._clear_audio_queue()
        finally:
            self.voip_device.set_is_active(False)

            # Allow pipeline to run again
            self._pipeline_task = None

    def _clear_audio_queue(self) -> None:
        """Ensure audio queue is empty."""
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Set state based on pipeline stage."""
        if event.type == PipelineEventType.STT_END:
            if (self._tones & Tones.PROCESSING) == Tones.PROCESSING:
                self._processing_tone_done.clear()
                self.config_entry.async_create_background_task(
                    self.hass, self._play_tone(Tones.PROCESSING), "voip_process_tone"
                )
        elif event.type == PipelineEventType.TTS_END:
            # Send TTS audio to caller over RTP
            if event.data and (tts_output := event.data["tts_output"]):
                media_id = tts_output["media_id"]
                self.config_entry.async_create_background_task(
                    self.hass,
                    self._send_tts(media_id),
                    "voip_pipeline_tts",
                )
            else:
                # Empty TTS response
                self._tts_done.set()
        elif event.type == PipelineEventType.ERROR:
            # Play error tone instead of wait for TTS when pipeline is finished.
            self._pipeline_had_error = True

    async def _send_tts(self, media_id: str) -> None:
        """Send TTS audio to caller via RTP."""
        try:
            if self.transport is None:
                return  # not connected

            extension, data = await tts.async_get_media_source_audio(
                self.hass,
                media_id,
            )

            if extension != "wav":
                raise ValueError(f"Only WAV audio can be streamed, got {extension}")

            if (self._tones & Tones.PROCESSING) == Tones.PROCESSING:
                # Don't overlap TTS and processing beep
                await self._processing_tone_done.wait()

            with io.BytesIO(data) as wav_io:
                with wave.open(wav_io, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    sample_width = wav_file.getsampwidth()
                    sample_channels = wav_file.getnchannels()

                    if (
                        (sample_rate != RATE)
                        or (sample_width != WIDTH)
                        or (sample_channels != CHANNELS)
                    ):
                        raise ValueError(
                            f"Expected rate/width/channels as {RATE}/{WIDTH}/{CHANNELS},"
                            f" got {sample_rate}/{sample_width}/{sample_channels}"
                        )

                audio_bytes = wav_file.readframes(wav_file.getnframes())

            _LOGGER.debug("Sending %s byte(s) of audio", len(audio_bytes))

            # Time out 1 second after TTS audio should be finished
            tts_samples = len(audio_bytes) / (WIDTH * CHANNELS)
            tts_seconds = tts_samples / RATE

            async with asyncio.timeout(tts_seconds + self._tts_extra_timeout):
                # TTS audio is 16Khz 16-bit mono
                await self._async_send_audio(audio_bytes)
        except TimeoutError:
            _LOGGER.warning("TTS timeout")
            raise
        finally:
            # Signal pipeline to restart
            self._tts_done.set()

            # Update satellite state
            self.tts_response_finished()

    async def _async_send_audio(self, audio_bytes: bytes, **kwargs):
        """Send audio in executor."""
        await self.hass.async_add_executor_job(
            partial(self.send_audio, audio_bytes, **RTP_AUDIO_SETTINGS, **kwargs)
        )

    async def _play_tone(self, tone: Tones, silence_before: float = 0.0) -> None:
        """Play a tone as feedback to the user if it's enabled."""
        if (self._tones & tone) != tone:
            return  # not enabled

        if tone not in self._tone_bytes:
            # Do I/O in executor
            self._tone_bytes[tone] = await self.hass.async_add_executor_job(
                self._load_pcm,
                _TONE_FILENAMES[tone],
            )

        await self._async_send_audio(
            self._tone_bytes[tone],
            silence_before=silence_before,
        )

        if tone == Tones.PROCESSING:
            self._processing_tone_done.set()

    def _load_pcm(self, file_name: str) -> bytes:
        """Load raw audio (16Khz, 16-bit mono)."""
        return (Path(__file__).parent / file_name).read_bytes()
