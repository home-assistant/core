"""Test configuration for http."""

import pytest

from tests.typing import ClientSessionGenerator


@pytest.fixture
def aiohttp_client(
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client
