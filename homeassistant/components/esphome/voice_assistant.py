"""ESPHome voice assistant support."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
import socket
from typing import cast

from homeassistant.components import stt, voice_assistant
from homeassistant.core import HomeAssistant, callback

from .entry_data import RuntimeEntryData


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
        if self.queue:
            self.queue.put_nowait(data)

    def error_received(self, exc) -> None:
        """Handle when a send or receive operation raises an OSError.

        (Other than BlockingIOError or InterruptedError.)
        """
        # TODO error handling
        print(exc)

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

    async def run_pipeline(self) -> None:
        """Run the Voice Assistant pipeline."""

        @callback
        def handle_pipeline_event(event: voice_assistant.PipelineEvent) -> None:
            """Handle pipeline events."""

            if event.type not in (
                voice_assistant.PipelineEventType.RUN_END,
                voice_assistant.PipelineEventType.ERROR,
            ):
                return

            # TODO We're done. Send message to ESPHome device

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
