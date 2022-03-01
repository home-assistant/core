"""Fixtures for Samsung TV."""
import asyncio
from datetime import datetime
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from samsungctl import Remote
from samsungtvws.async_connection import SamsungTVWSAsyncConnection
from samsungtvws.command import SamsungTVCommand
from samsungtvws.event import ED_INSTALLED_APP_EVENT

import homeassistant.util.dt as dt_util

from tests.common import load_fixture


class MockAsyncWebsocket:
    """Class to mock a websockets."""

    def __init__(self):
        """Initialise MockAsyncWebsocket."""
        self.app_list_return = json.loads(
            load_fixture("samsungtv/ed_installedApp_get.json")
        )
        self.closed = True
        self.callback = None

    async def start_listening(self, callback):
        """Mock successful start_listening."""
        self.callback = callback
        self.closed = False

    async def close(self):
        """Mock successful close."""
        self.callback = None
        self.closed = True

    async def send_command(self, command: SamsungTVCommand):
        """Mock status based on failure mode."""
        if command.method == "ms.channel.emit":
            if command.params == {
                "event": "ed.installedApp.get",
                "to": "host",
            }:
                asyncio.ensure_future(
                    self.callback(ED_INSTALLED_APP_EVENT, self.app_list_return)
                )


@pytest.fixture(autouse=True)
def fake_host_fixture() -> None:
    """Patch gethostbyname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        yield


@pytest.fixture(name="remote")
def remote_fixture() -> Mock:
    """Patch the samsungctl Remote."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote_class:
        remote = Mock(Remote)
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote_class.return_value = remote
        yield remote


@pytest.fixture(name="rest_api", autouse=True)
def rest_api_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVAsyncRest."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        autospec=True,
    ) as rest_api_class:
        rest_api_class.return_value.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SmartTV",
                "networkType": "wireless",
            },
        }
        yield rest_api_class.return_value


@pytest.fixture(name="ws_connection")
def ws_connection_fixture() -> MockAsyncWebsocket:
    """Patch the samsungtvws SamsungTVWS."""
    ws_connection = MockAsyncWebsocket()
    yield ws_connection


@pytest.fixture(name="remotews")
def remotews_fixture(ws_connection: MockAsyncWebsocket) -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncConnection",
    ) as remotews_class:
        remotews = Mock(SamsungTVWSAsyncConnection)
        remotews.__aenter__ = AsyncMock(return_value=remotews)
        remotews.__aexit__ = AsyncMock()
        remotews.connection = ws_connection
        remotews.start_listening.side_effect = ws_connection.start_listening
        remotews.send_command.side_effect = ws_connection.send_command
        remotews.token = "FAKE_TOKEN"
        remotews_class.return_value = remotews
        yield remotews


@pytest.fixture(name="delay")
def delay_fixture() -> Mock:
    """Patch the delay script function."""
    with patch(
        "homeassistant.components.samsungtv.media_player.Script.async_run"
    ) as delay:
        yield delay


@pytest.fixture
def mock_now() -> datetime:
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


@pytest.fixture(name="no_mac_address")
def mac_address_fixture() -> Mock:
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
