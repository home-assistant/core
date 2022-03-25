"""Fixtures for Samsung TV."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from samsungctl import Remote
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.command import SamsungTVCommand
from samsungtvws.encrypted.remote import SamsungTVEncryptedWSAsyncRemote
from samsungtvws.event import ED_INSTALLED_APP_EVENT
from samsungtvws.remote import ChannelEmitCommand

import homeassistant.util.dt as dt_util

from .const import SAMPLE_DEVICE_INFO_WIFI


@pytest.fixture(autouse=True)
def fake_host_fixture() -> None:
    """Patch gethostbyname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        yield


@pytest.fixture(autouse=True)
def app_list_delay_fixture() -> None:
    """Patch APP_LIST_DELAY."""
    with patch("homeassistant.components.samsungtv.media_player.APP_LIST_DELAY", 0):
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
        rest_api_class.return_value.rest_device_info.return_value = (
            SAMPLE_DEVICE_INFO_WIFI
        )
        yield rest_api_class.return_value


@pytest.fixture(name="remotews")
def remotews_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    remotews = Mock(SamsungTVWSAsyncRemote)
    remotews.__aenter__ = AsyncMock(return_value=remotews)
    remotews.__aexit__ = AsyncMock()
    remotews.token = "FAKE_TOKEN"
    remotews.app_list_data = None

    async def _start_listening(
        ws_event_callback: Callable[[str, Any], Awaitable[None] | None] | None = None
    ):
        remotews.ws_event_callback = ws_event_callback

    async def _send_commands(commands: list[SamsungTVCommand]):
        if (
            len(commands) == 1
            and isinstance(commands[0], ChannelEmitCommand)
            and commands[0].params["event"] == "ed.installedApp.get"
            and remotews.app_list_data is not None
        ):
            remotews.raise_mock_ws_event_callback(
                ED_INSTALLED_APP_EVENT,
                remotews.app_list_data,
            )

    def _mock_ws_event_callback(event: str, response: Any):
        if remotews.ws_event_callback:
            remotews.ws_event_callback(event, response)

    remotews.start_listening.side_effect = _start_listening
    remotews.send_commands.side_effect = _send_commands
    remotews.raise_mock_ws_event_callback = Mock(side_effect=_mock_ws_event_callback)

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
    ) as remotews_class:
        remotews_class.return_value = remotews
        yield remotews


@pytest.fixture(name="remoteencws")
def remoteencws_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVEncryptedWSAsyncRemote."""
    remoteencws = Mock(SamsungTVEncryptedWSAsyncRemote)
    remoteencws.__aenter__ = AsyncMock(return_value=remoteencws)
    remoteencws.__aexit__ = AsyncMock()

    def _start_listening(
        ws_event_callback: Callable[[str, Any], Awaitable[None] | None] | None = None
    ):
        remoteencws.ws_event_callback = ws_event_callback

    def _mock_ws_event_callback(event: str, response: Any):
        if remoteencws.ws_event_callback:
            remoteencws.ws_event_callback(event, response)

    remoteencws.start_listening.side_effect = _start_listening
    remoteencws.raise_mock_ws_event_callback = Mock(side_effect=_mock_ws_event_callback)

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote",
    ) as remotews_class:
        remotews_class.return_value = remoteencws
        yield remoteencws


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


@pytest.fixture(name="mac_address", autouse=True)
def mac_address_fixture() -> Mock:
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
