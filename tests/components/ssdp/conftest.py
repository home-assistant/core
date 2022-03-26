"""Configuration for SSDP tests."""
from unittest.mock import AsyncMock, patch

from async_upnp_client.ssdp_listener import SsdpListener
import pytest


@pytest.fixture(autouse=True)
async def silent_ssdp_listener():
    """Patch SsdpListener class, preventing any actual SSDP traffic."""
    with patch("homeassistant.components.ssdp.SsdpListener.async_start"), patch(
        "homeassistant.components.ssdp.SsdpListener.async_stop"
    ), patch("homeassistant.components.ssdp.SsdpListener.async_search"):
        # Fixtures are initialized before patches. When the component is started here,
        # certain functions/methods might not be patched in time.
        yield SsdpListener


@pytest.fixture
def mock_flow_init(hass):
    """Mock hass.config_entries.flow.async_init."""
    with patch.object(
        hass.config_entries.flow, "async_init", return_value=AsyncMock()
    ) as mock_init:
        yield mock_init
