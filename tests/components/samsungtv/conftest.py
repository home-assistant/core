"""Fixtures for Samsung TV."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from socket import AddressFamily
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from async_upnp_client.client import UpnpDevice
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.exceptions import UpnpConnectionError
import pytest
from samsungctl import Remote
from samsungtvws.async_remote import SamsungTVWSAsyncRemote
from samsungtvws.command import SamsungTVCommand
from samsungtvws.encrypted.remote import SamsungTVEncryptedWSAsyncRemote
from samsungtvws.event import ED_INSTALLED_APP_EVENT
from samsungtvws.exceptions import ResponseError
from samsungtvws.remote import ChannelEmitCommand

from homeassistant.components.samsungtv.const import WEBSOCKET_SSL_PORT
import homeassistant.util.dt as dt_util

from .const import SAMPLE_DEVICE_INFO_UE48JU6400, SAMPLE_DEVICE_INFO_WIFI


@pytest.fixture(autouse=True)
async def silent_ssdp_scanner(hass):
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with patch(
        "homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"
    ), patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"), patch(
        "homeassistant.components.ssdp.Scanner.async_scan"
    ):
        yield


@pytest.fixture(autouse=True)
def samsungtv_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""


@pytest.fixture(autouse=True)
def samsungtv_mock_async_get_local_ip():
    """Mock upnp util's async_get_local_ip."""
    with patch(
        "homeassistant.components.samsungtv.media_player.async_get_local_ip",
        return_value=(AddressFamily.AF_INET, "10.10.10.10"),
    ):
        yield


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


@pytest.fixture(name="upnp_factory", autouse=True)
def upnp_factory_fixture() -> Mock:
    """Patch UpnpFactory."""
    with patch(
        "homeassistant.components.samsungtv.media_player.UpnpFactory",
        autospec=True,
    ) as upnp_factory_class:
        upnp_factory: Mock = upnp_factory_class.return_value
        upnp_factory.async_create_device.side_effect = UpnpConnectionError
        yield upnp_factory


@pytest.fixture(name="upnp_device")
async def upnp_device_fixture(upnp_factory: Mock) -> Mock:
    """Patch async_upnp_client."""
    upnp_device = Mock(UpnpDevice)
    upnp_device.services = {}

    with patch.object(upnp_factory, "async_create_device", side_effect=[upnp_device]):
        yield upnp_device


@pytest.fixture(name="dmr_device")
async def dmr_device_fixture(upnp_device: Mock) -> Mock:
    """Patch async_upnp_client."""
    with patch(
        "homeassistant.components.samsungtv.media_player.DmrDevice",
        autospec=True,
    ) as dmr_device_class:
        dmr_device: Mock = dmr_device_class.return_value
        dmr_device.volume_level = 0.44
        dmr_device.is_volume_muted = False
        dmr_device.on_event = None
        dmr_device.is_subscribed = False

        def _raise_event(service, state_variables):
            if dmr_device.on_event:
                dmr_device.on_event(service, state_variables)

        dmr_device.raise_event = _raise_event

        def _async_subscribe_services(auto_resubscribe: bool = False):
            dmr_device.is_subscribed = True

        dmr_device.async_subscribe_services = AsyncMock(
            side_effect=_async_subscribe_services
        )

        def _async_unsubscribe_services():
            dmr_device.is_subscribed = False

        dmr_device.async_unsubscribe_services = AsyncMock(
            side_effect=_async_unsubscribe_services
        )
        yield dmr_device


@pytest.fixture(name="upnp_notify_server")
async def upnp_notify_server_fixture(upnp_factory: Mock) -> Mock:
    """Patch async_upnp_client."""
    with patch(
        "homeassistant.components.samsungtv.media_player.AiohttpNotifyServer",
        autospec=True,
    ) as notify_server_class:
        notify_server: Mock = notify_server_class.return_value
        notify_server.event_handler = Mock(UpnpEventHandler)
        yield notify_server


@pytest.fixture(name="remote")
def remote_fixture() -> Mock:
    """Patch the samsungctl Remote."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote_class:
        remote = Mock(Remote)
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote_class.return_value = remote
        yield remote


@pytest.fixture(name="rest_api")
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


@pytest.fixture(name="rest_api_non_ssl_only")
def rest_api_fixture_non_ssl_only() -> Mock:
    """Patch the samsungtvws SamsungTVAsyncRest non-ssl only."""

    class MockSamsungTVAsyncRest:
        """Mock for a MockSamsungTVAsyncRest."""

        def __init__(self, host, session, port, timeout):
            """Mock a MockSamsungTVAsyncRest."""
            self.port = port
            self.host = host

        async def rest_device_info(self):
            """Mock rest_device_info to fail for ssl and work for non-ssl."""
            if self.port == WEBSOCKET_SSL_PORT:
                raise ResponseError
            return SAMPLE_DEVICE_INFO_UE48JU6400

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        MockSamsungTVAsyncRest,
    ):
        yield


@pytest.fixture(name="rest_api_failing")
def rest_api_failure_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVAsyncRest."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        autospec=True,
    ) as rest_api_class:
        rest_api_class.return_value.rest_device_info.side_effect = ResponseError
        yield


@pytest.fixture(name="remoteencws_failing")
def remoteencws_failing_fixture():
    """Patch the samsungtvws SamsungTVEncryptedWSAsyncRemote."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
        side_effect=OSError,
    ):
        yield


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
