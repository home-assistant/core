"""Mock of Imazu Wall Pad client."""
import asyncio
from unittest.mock import AsyncMock, Mock

from wp_imazu.client import ImazuClient


class MockImazuClient(ImazuClient):
    """Mock of Imazu Wall Pad client."""

    _writer: asyncio.StreamWriter

    async def async_connect(self) -> bool:
        """Connect."""
        self.connected = True
        self._writer = Mock()
        return AsyncMock(return_value=True)

    async def async_send(self, packet: bytes) -> None:
        """Socket write imazu packet."""

    async def async_send_wait(self, packet: bytes) -> None:
        """Socket write imazu packet and response wait."""

    async def async_receive_packet(self, packet: bytes) -> None:
        """Receive test packet."""
        await self.async_receive_handler(packet)
