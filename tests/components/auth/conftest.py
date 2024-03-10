"""Test configuration for auth."""

import pytest


@pytest.fixture
def aiohttp_client(event_loop, aiohttp_client, socket_enabled):
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client
