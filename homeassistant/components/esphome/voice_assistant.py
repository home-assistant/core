"""ESPHome voice assistant support."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
import logging
import socket
from typing import cast

from aioesphomeapi import VoiceAssistantEventType

from homeassistant.components import stt
from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventType,
    async_pipeline_from_audio_stream,
)
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import Context, HomeAssistant, callback

from .enum_mapper import EsphomeEnumMapper

_LOGGER = logging.getLogger(__name__)

UDP_PORT = 0  # Set to 0 to let the OS pick a free random port

_VOICE_ASSISTANT_EVENT_TYPES: EsphomeEnumMapper[
    VoiceAssistantEventType, PipelineEventType
] = EsphomeEnumMapper(
    {
        VoiceAssistantEventType.VOICE_ASSISTANT_ERROR: PipelineEventType.ERROR,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START: PipelineEventType.RUN_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END: PipelineEventType.RUN_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_START: PipelineEventType.STT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_END: PipelineEventType.STT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_START: PipelineEventType.INTENT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END: PipelineEventType.INTENT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START: PipelineEventType.TTS_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END: PipelineEventType.TTS_END,
    }
)


class VoiceAssistantUDPServer(asyncio.DatagramProtocol):
    """Receive UDP packets and forward them to the voice assistant."""

    started = False
    queue: asyncio.Queue[bytes] | None = None
    transport: asyncio.DatagramTransport | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize UDP receiver."""
        self.context = Context()
        self.hass = hass
        self.queue = asyncio.Queue()

    async def start_server(self) -> int:
        """Start accepting connections."""

        def accept_connection() -> VoiceAssistantUDPServer:
            """Accept connection."""
            if self.started:
                raise RuntimeError("Can only start once")
            if self.queue is None:
                raise RuntimeError("No longer accepting connections")

            self.started = True
            return self

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        sock.bind(("", UDP_PORT))

        await asyncio.get_running_loop().create_datagram_endpoint(
            accept_connection, sock=sock
        )

        return cast(int, sock.getsockname()[1])

    @callback
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store transport for later use."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    @callback
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP packet."""
        if self.queue is not None:
            self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        """Handle when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        _LOGGER.error("ESPHome Voice Assistant UDP server error received: %s", exc)

    @callback
    def stop(self) -> None:
        """Stop the receiver."""
        if self.queue is not None:
            self.queue.put_nowait(b"")
            self.queue = None
        if self.transport is not None:
            self.transport.close()

    async def _iterate_packets(self) -> AsyncIterable[bytes]:
        """Iterate over incoming packets."""
        if self.queue is None:
            raise RuntimeError("Already stopped")

        while data := await self.queue.get():
            yield data

    async def run_pipeline(
        self,
        handle_event: Callable[[VoiceAssistantEventType, dict[str, str] | None], None],
    ) -> None:
        """Run the Voice Assistant pipeline."""

        @callback
        def handle_pipeline_event(event: PipelineEvent) -> None:
            """Handle pipeline events."""

            try:
                event_type = _VOICE_ASSISTANT_EVENT_TYPES.from_hass(event.type)
            except KeyError:
                _LOGGER.warning("Received unknown pipeline event type: %s", event.type)
                return

            data_to_send = None
            if event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
                assert event.data is not None
                data_to_send = {"text": event.data["stt_output"]["text"]}
            elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START:
                assert event.data is not None
                data_to_send = {"text": event.data["tts_input"]}
            elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END:
                assert event.data is not None
                path = event.data["tts_output"]["url"]
                url = async_process_play_media_url(self.hass, path)
                data_to_send = {"url": url}
            elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
                assert event.data is not None
                data_to_send = {
                    "code": event.data["code"],
                    "message": event.data["message"],
                }

            handle_event(event_type, data_to_send)

        await async_pipeline_from_audio_stream(
            self.hass,
            context=self.context,
            event_callback=handle_pipeline_event,
            stt_metadata=stt.SpeechMetadata(
                language="",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=self._iterate_packets(),
        )
