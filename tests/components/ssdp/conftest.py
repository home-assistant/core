"""Configuration for SSDP tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from async_upnp_client.server import UpnpServer
from async_upnp_client.ssdp_listener import SsdpListener
import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def silent_ssdp_listener():
    """Patch SsdpListener class, preventing any actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.scanner.SsdpListener.async_start"),
        patch("homeassistant.components.ssdp.scanner.SsdpListener.async_stop"),
        patch("homeassistant.components.ssdp.scanner.SsdpListener.async_search"),
    ):
        # Fixtures are initialized before patches. When the component is started here,
        # certain functions/methods might not be patched in time.
        yield SsdpListener


@pytest.fixture(autouse=True)
async def disabled_upnp_server():
    """Disable UPnpServer."""
    with (
        patch("homeassistant.components.ssdp.server.UpnpServer.async_start"),
        patch("homeassistant.components.ssdp.server.UpnpServer.async_stop"),
        patch("homeassistant.components.ssdp.server._async_find_next_available_port"),
    ):
        yield UpnpServer


@pytest.fixture
def mock_flow_init(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Mock hass.config_entries.flow.async_init."""
    with patch.object(
        hass.config_entries.flow, "async_init", return_value=AsyncMock()
    ) as mock_init:
        yield mock_init
