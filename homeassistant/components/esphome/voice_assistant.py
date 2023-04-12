"""ESPHome voice assistant support."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
import logging
import socket
from typing import Any, cast

from aioesphomeapi import VoiceAssistantEventType

from homeassistant.components import stt, voice_assistant
from homeassistant.core import HomeAssistant, callback

from .entry_data import RuntimeEntryData
from .enum_mapper import EsphomeEnumMapper

_LOGGER = logging.getLogger(__name__)

_VOICE_ASSISTANT_EVENT_TYPES: EsphomeEnumMapper[
    VoiceAssistantEventType, voice_assistant.PipelineEventType
] = EsphomeEnumMapper(
    {
        VoiceAssistantEventType.VOICE_ASSISTANT_ERROR: voice_assistant.PipelineEventType.ERROR,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START: voice_assistant.PipelineEventType.RUN_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END: voice_assistant.PipelineEventType.RUN_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_START: voice_assistant.PipelineEventType.STT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_STT_END: voice_assistant.PipelineEventType.STT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_START: voice_assistant.PipelineEventType.INTENT_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END: voice_assistant.PipelineEventType.INTENT_END,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START: voice_assistant.PipelineEventType.TTS_START,
        VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END: voice_assistant.PipelineEventType.TTS_END,
    }
)


class VoiceAssistantUDPServer(asyncio.DatagramProtocol):
    """Receive UDP packets and forward them to the voice assistant."""

    started = False
    queue: asyncio.Queue[bytes] | None = None
    transport: asyncio.DatagramTransport | None = None

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize UDP receiver."""
        self.hass = hass
        self.entry_data = entry_data
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

        sock.bind(("", 0))

        await asyncio.get_running_loop().create_datagram_endpoint(
            accept_connection, sock=sock
        )

        return cast(int, sock.getsockname()[1])

    @callback
    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Store transport for later use."""
        self.transport = transport

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
        handle_event: Callable[[VoiceAssistantEventType, dict[str, Any] | None], None],
    ) -> None:
        """Run the Voice Assistant pipeline."""

        @callback
        def handle_pipeline_event(event: voice_assistant.PipelineEvent) -> None:
            """Handle pipeline events."""

            event_type = _VOICE_ASSISTANT_EVENT_TYPES.from_hass(event.type)
            handle_event(event_type, event.data)

        await voice_assistant.async_pipeline_from_audio_stream(
            self.hass,
            handle_pipeline_event,
            stt.SpeechMetadata(
                language="",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            self._iterate_packets(),
        )
