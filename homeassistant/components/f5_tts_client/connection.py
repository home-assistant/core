"""Socket handling."""

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 15


class ConnectionClient:
    """Socket client for the TTS server."""

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    def __init__(self, host, port) -> None:
        """Set connection details."""
        self.host = host
        self.port = port

    async def connect(self):
        """Connect to server."""
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port, limit=1
        )
        _LOGGER.debug("Connected to %s:%s", self.host, self.port)

    async def send_message(self, message: str):
        """Send message to server."""
        self.writer.write(message.encode())
        await asyncio.wait_for(self.writer.drain(), timeout=TIMEOUT)

    async def receive_message(self, chunk_size: int, terminator: bytes):
        """Parse reaver stream from server."""
        audio_data = bytearray()
        while True:
            chunk = await asyncio.wait_for(
                self.reader.read(chunk_size), timeout=TIMEOUT
            )

            if terminator in chunk:
                chunk, _ = chunk.split(terminator, 1)
                audio_data.extend(chunk)
                break
            audio_data.extend(chunk)

        return bytes(audio_data)

    async def disconnect(self):
        """Disconnect the socket."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        _LOGGER.debug("Disconnected from %s:%s", self.host, self.port)
