"""socket_util."""
import asyncio
from collections.abc import Callable
import json
import logging
import socket
from typing import cast

LOGGER = logging.getLogger(__name__)


def socket_init() -> socket.socket:
    """socket_init."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", 9989))
    return sock


class SocketServerProtocol(asyncio.DatagramProtocol):
    """Socket server."""
    def register_message_received(
        self, message_received: Callable | None = None
    ) -> None:
        """Register message received."""
        self._message_received = message_received

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle connection made."""
        self.transport = cast(asyncio.DatagramTransport, transport)

    async def initialize(self) -> None:
        """Initialize socket server."""
        loop = asyncio.get_running_loop()
        self.sock = socket_init()
        await loop.create_datagram_endpoint(lambda: self, sock=self.sock)

    async def broadcast_msg(self) -> None:
        """Broadcast."""
        address = ("255.255.255.255", 9988)
        msg = json.dumps(
            {"id": "48cbd88f969eb3c486085cfe7b5eb1e4", "devName": "*"}
        ).encode("utf-8")
        while True:
            self.transport.sendto(msg, address)
            await asyncio.sleep(10)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming datagram messages."""
        json_str = format(data.decode("utf-8"))

        data_dict = json.loads(json_str)
        if self._message_received:
            self._message_received(data_dict)

    def close(self) -> None:
        """Close."""
        if self.transport is not None:
            self.transport.close()

        self.transport = None
        self.sock = None
