"""Fixtures for Samsung TV."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from socket import AddressFamily  # pylint: disable=no-name-in-module
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

from homeassistant.components.samsungtv.const import DOMAIN, WEBSOCKET_SSL_PORT

from .const import SAMPLE_DEVICE_INFO_WIFI

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.samsungtv.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def samsungtv_mock_async_get_local_ip() -> Generator[None]:
    """Mock upnp util's async_get_local_ip."""
    with patch(
        "homeassistant.components.samsungtv.media_player.async_get_local_ip",
        return_value=(AddressFamily.AF_INET, "10.10.10.10"),
    ):
        yield


@pytest.fixture(autouse=True)
def fake_host_fixture() -> Generator[None]:
    """Patch gethostbyname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        yield


@pytest.fixture(autouse=True)
def app_list_delay_fixture() -> Generator[None]:
    """Patch APP_LIST_DELAY."""
    with patch("homeassistant.components.samsungtv.media_player.APP_LIST_DELAY", 0):
        yield


@pytest.fixture(name="upnp_factory", autouse=True)
def upnp_factory_fixture() -> Generator[Mock]:
    """Patch UpnpFactory."""
    with patch(
        "homeassistant.components.samsungtv.media_player.UpnpFactory",
        autospec=True,
    ) as upnp_factory_class:
        upnp_factory: Mock = upnp_factory_class.return_value
        upnp_factory.async_create_device.side_effect = UpnpConnectionError
        yield upnp_factory


@pytest.fixture(name="upnp_device")
def upnp_device_fixture(upnp_factory: Mock) -> Mock:
    """Patch async_upnp_client."""
    upnp_device = Mock(UpnpDevice)
    upnp_device.services = {}

    upnp_factory.async_create_device.side_effect = [upnp_device]
    return upnp_device


@pytest.fixture(name="dmr_device")
def dmr_device_fixture(upnp_device: Mock) -> Generator[Mock]:
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
def upnp_notify_server_fixture(upnp_factory: Mock) -> Generator[Mock]:
    """Patch async_upnp_client."""
    with patch(
        "homeassistant.components.samsungtv.media_player.AiohttpNotifyServer",
        autospec=True,
    ) as notify_server_class:
        notify_server: Mock = notify_server_class.return_value
        notify_server.event_handler = Mock(UpnpEventHandler)
        yield notify_server


@pytest.fixture(name="remote_legacy")
def remote_legacy_fixture() -> Generator[Mock]:
    """Patch the samsungctl Remote."""
    remote_legacy = Mock(Remote)
    remote_legacy.__enter__ = Mock()
    remote_legacy.__exit__ = Mock()
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote", return_value=remote_legacy
    ):
        yield remote_legacy


@pytest.fixture(name="rest_api")
def rest_api_fixture() -> Generator[Mock]:
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
def rest_api_fixture_non_ssl_only() -> Generator[None]:
    """Patch the samsungtvws SamsungTVAsyncRest non-ssl only."""

    class MockSamsungTVAsyncRest:
        """Mock for a MockSamsungTVAsyncRest."""

        def __init__(self, host, session, port, timeout) -> None:
            """Mock a MockSamsungTVAsyncRest."""
            self.port = port
            self.host = host

        async def rest_device_info(self):
            """Mock rest_device_info to fail for ssl and work for non-ssl."""
            if self.port == WEBSOCKET_SSL_PORT:
                raise ResponseError
            return load_json_object_fixture("device_info_UE48JU6400.json", DOMAIN)

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        MockSamsungTVAsyncRest,
    ):
        yield


@pytest.fixture(name="rest_api_failing")
def rest_api_failure_fixture() -> Generator[None]:
    """Patch the samsungtvws SamsungTVAsyncRest."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        autospec=True,
    ) as rest_api_class:
        rest_api_class.return_value.rest_device_info.side_effect = ResponseError
        yield


@pytest.fixture(name="remoteencws_failing")
def remoteencws_failing_fixture() -> Generator[None]:
    """Patch the samsungtvws SamsungTVEncryptedWSAsyncRemote."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote.start_listening",
        side_effect=OSError,
    ):
        yield


@pytest.fixture(name="remote_websocket")
def remote_websocket_fixture() -> Generator[Mock]:
    """Patch the samsungtvws SamsungTVWS."""
    remote_websocket = Mock(SamsungTVWSAsyncRemote)
    remote_websocket.__aenter__ = AsyncMock(return_value=remote_websocket)
    remote_websocket.__aexit__ = AsyncMock()
    remote_websocket.token = "FAKE_TOKEN"
    remote_websocket.app_list_data = None

    async def _start_listening(
        ws_event_callback: Callable[[str, Any], Awaitable[None] | None] | None = None,
    ):
        remote_websocket.ws_event_callback = ws_event_callback

    async def _send_commands(commands: list[SamsungTVCommand]):
        if (
            len(commands) == 1
            and isinstance(commands[0], ChannelEmitCommand)
            and commands[0].params["event"] == "ed.installedApp.get"
            and remote_websocket.app_list_data is not None
        ):
            remote_websocket.raise_mock_ws_event_callback(
                ED_INSTALLED_APP_EVENT,
                remote_websocket.app_list_data,
            )

    def _mock_ws_event_callback(event: str, response: Any):
        if remote_websocket.ws_event_callback:
            remote_websocket.ws_event_callback(event, response)

    remote_websocket.start_listening.side_effect = _start_listening
    remote_websocket.send_commands.side_effect = _send_commands
    remote_websocket.raise_mock_ws_event_callback = Mock(
        side_effect=_mock_ws_event_callback
    )

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
        return_value=remote_websocket,
    ):
        yield remote_websocket


@pytest.fixture(name="remote_encrypted_websocket")
def remote_encrypted_websocket_fixture() -> Generator[Mock]:
    """Patch the samsungtvws SamsungTVEncryptedWSAsyncRemote."""
    remote_encrypted_websocket = Mock(SamsungTVEncryptedWSAsyncRemote)
    remote_encrypted_websocket.__aenter__ = AsyncMock(
        return_value=remote_encrypted_websocket
    )
    remote_encrypted_websocket.__aexit__ = AsyncMock()

    def _start_listening(
        ws_event_callback: Callable[[str, Any], Awaitable[None] | None] | None = None,
    ):
        remote_encrypted_websocket.ws_event_callback = ws_event_callback

    def _mock_ws_event_callback(event: str, response: Any):
        if remote_encrypted_websocket.ws_event_callback:
            remote_encrypted_websocket.ws_event_callback(event, response)

    remote_encrypted_websocket.start_listening.side_effect = _start_listening
    remote_encrypted_websocket.raise_mock_ws_event_callback = Mock(
        side_effect=_mock_ws_event_callback
    )

    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVEncryptedWSAsyncRemote",
    ) as remotews_class:
        remotews_class.return_value = remote_encrypted_websocket
        yield remote_encrypted_websocket


@pytest.fixture(name="mac_address", autouse=True)
def mac_address_fixture() -> Generator[Mock]:
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
