"""Test configuration for auth."""

from asyncio import AbstractEventLoop

import pytest

from tests.typing import ClientSessionGenerator


@pytest.fixture
def aiohttp_client(
    event_loop: AbstractEventLoop,
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client
