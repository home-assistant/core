"""Test configuration and mocks for LinkPlay component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge, LinkPlayDevice, LinkPlayMultiroom
from linkplay.endpoint import LinkPlayApiEndpoint
import pytest

from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

HOST = "10.0.0.150"
HOST_REENTRY = "10.0.0.66"
UUID = "FF31F09E-5001-FBDE-0546-2DBFFF31F09E"
NAME = "Smart Zone 1_54B9"


@pytest.fixture
def mock_linkplay_factory_bridge_init() -> Generator[AsyncMock]:
    """Mock for linkplay_factory_httpapi_bridge."""

    with (
        patch(
            "homeassistant.components.linkplay.async_get_client_session",
            return_value=AsyncMock(spec=ClientSession),
        ),
        patch(
            "homeassistant.components.linkplay.linkplay_factory_httpapi_bridge",
            return_value=AsyncMock(spec=ClientSession),
        ) as init_factory,
        patch.object(LinkPlayDevice, "update_status", return_value=None),
        patch.object(LinkPlayMultiroom, "update_status", return_value=None),
    ):
        bridge = LinkPlayBridge(
            endpoint=LinkPlayApiEndpoint(protocol="http", endpoint=HOST, session=None)
        )
        bridge.device = LinkPlayDevice(bridge)
        init_factory.return_value = bridge
        yield init_factory


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
        ) as conf_factory,
    ):
        bridge = AsyncMock(spec=LinkPlayBridge)
        bridge.endpoint = HOST
        bridge.device = AsyncMock(spec=LinkPlayDevice)
        bridge.device.uuid = UUID
        bridge.device.name = NAME
        conf_factory.return_value = bridge
        yield conf_factory


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.linkplay.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST},
        unique_id=UUID,
    )
