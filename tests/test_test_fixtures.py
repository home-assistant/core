"""Test test fixture configuration."""

from collections.abc import Generator
from http import HTTPStatus
import pathlib
import socket

from aiohttp import web
import pytest
import pytest_socket

from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.helpers import translation
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.setup import async_setup_component

from .common import MockModule, mock_integration
from .conftest import evict_faked_translations
from .typing import ClientSessionGenerator


def test_sockets_disabled() -> None:
    """Test we can't open sockets."""
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket()


@pytest.mark.usefixtures("socket_enabled")
def test_sockets_enabled() -> None:
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


async def test_evict_faked_translations_assumptions(hass: HomeAssistant) -> None:
    """Test assumptions made when detecting translations for mocked integrations.

    If this test fails, the evict_faked_translations may need to be updated.
    """
    integration = mock_integration(hass, MockModule("test"), built_in=True)
    assert integration.file_path == pathlib.Path("")


async def test_evict_faked_translations(hass: HomeAssistant, translations_once) -> None:
    """Test the evict_faked_translations fixture."""
    cache: translation._TranslationsCacheData = translations_once.kwargs["return_value"]
    fake_domain = "test"
    real_domain = "homeassistant"

    # Evict the real domain from the cache in case it's been loaded before
    cache.loaded["en"].discard(real_domain)

    assert fake_domain not in cache.loaded["en"]
    assert real_domain not in cache.loaded["en"]

    # The evict_faked_translations fixture has module scope, so we set it up and
    # tear it down manually
    real_func = evict_faked_translations.__pytest_wrapped__.obj
    gen: Generator = real_func(translations_once)

    # Set up the evict_faked_translations fixture
    next(gen)

    mock_integration(hass, MockModule(fake_domain), built_in=True)
    await translation.async_load_integrations(hass, {fake_domain, real_domain})
    assert fake_domain in cache.loaded["en"]
    assert real_domain in cache.loaded["en"]

    # Tear down the evict_faked_translations fixture
    with pytest.raises(StopIteration):
        next(gen)

    # The mock integration should be removed from the cache, the real domain should still be there
    assert fake_domain not in cache.loaded["en"]
    assert real_domain in cache.loaded["en"]
