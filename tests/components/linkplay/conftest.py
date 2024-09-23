"""Test configuration and mocks for LinkPlay component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge, LinkPlayDevice
import pytest

HOST = "10.0.0.150"
HOST_REENTRY = "10.0.0.66"
UUID = "FF31F09E-5001-FBDE-0546-2DBFFF31F09E"
NAME = "Smart Zone 1_54B9"


@pytest.fixture
def mock_linkplay_factory_bridge() -> Generator[AsyncMock]:
    """Mock for linkplay_factory_httpapi_bridge."""

    with (
        patch(
            "homeassistant.components.linkplay.config_flow.async_get_client_session",
            return_value=AsyncMock(spec=ClientSession),
        ),
        patch(
            "homeassistant.components.linkplay.config_flow.linkplay_factory_httpapi_bridge",
        ) as factory,
    ):
        bridge = AsyncMock(spec=LinkPlayBridge)
        bridge.endpoint = HOST
        bridge.device = AsyncMock(spec=LinkPlayDevice)
        bridge.device.uuid = UUID
        bridge.device.name = NAME
        factory.return_value = bridge
        yield factory


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.linkplay.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
