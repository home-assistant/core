"""Test test fixture configuration."""
from http import HTTPStatus
import socket

from aiohttp import web
import pytest
import pytest_socket

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.setup import async_setup_component

from .typing import ClientSessionGenerator


def test_sockets_disabled() -> None:
    """Test we can't open sockets."""
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket()


def test_sockets_enabled(socket_enabled) -> None:
    """Test we can't connect to an address different from 127.0.0.1."""
    mysocket = socket.socket()
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        mysocket.connect(("127.0.0.2", 1234))


async def test_hass_cv(hass: HomeAssistant) -> None:
    """Test hass context variable.

    When tests are using the `hass`, this tests that the hass context variable was set
    in the fixture and that async_get_hass() works correctly.
    """
    assert async_get_hass() is hass


def register_view(hass: HomeAssistant) -> None:
    """Register a view."""

    class TestView(HomeAssistantView):
        """Test view to serve the test."""

        requires_auth = False
        url = "/api/test"
        name = "api:test"

        async def get(self, request: web.Request) -> web.Response:
            """Return a test result."""
            return self.json({"test": True})

    hass.http.register_view(TestView())


async def test_aiohttp_client_frozen_router_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test aiohttp_client fixture patches frozen router for views."""
    assert await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()

    # Registering the view after starting the server should still work.
    client = await hass_client()
    register_view(hass)

    response = await client.get("/api/test")
    assert response.status == HTTPStatus.OK
    result = await response.json()
    assert result["test"] is True
