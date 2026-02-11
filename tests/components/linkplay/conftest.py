"""Test configuration and mocks for LinkPlay component."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession
from linkplay.bridge import LinkPlayBridge, LinkPlayDevice
import pytest

from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.conftest import AiohttpClientMocker

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


@pytest.fixture
def mock_player_ex(
    mock_player_ex: AsyncMock,
) -> AsyncMock:
    """Mock a update_status of the LinkPlayPlayer."""
    mock_player_ex.return_value = load_fixture("getPlayerEx.json", DOMAIN)
    return mock_player_ex


@pytest.fixture
def mock_status_ex(
    mock_status_ex: AsyncMock,
) -> AsyncMock:
    """Mock a update_status of the LinkPlayDevice."""
    mock_status_ex.return_value = load_fixture("getStatusEx.json", DOMAIN)
    return mock_status_ex


@contextmanager
def mock_lp_aiohttp_client() -> Iterator[AiohttpClientMocker]:
    """Context manager to mock aiohttp client."""
    mocker = AiohttpClientMocker()

    def create_session(hass: HomeAssistant, *args: Any, **kwargs: Any) -> ClientSession:
        session = mocker.create_session(hass.loop)

        async def close_session(event):
            """Close session."""
            await session.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, close_session)

        return session

    with mock.patch(
        "homeassistant.components.linkplay.async_get_client_session",
        side_effect=create_session,
    ):
        yield mocker
