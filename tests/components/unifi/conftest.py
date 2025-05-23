"""Fixtures for UniFi Network methods."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Generator
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Protocol
from unittest.mock import AsyncMock, patch

from aiounifi.models.message import MessageKey
import orjson
import pytest

from homeassistant.components.unifi import STORAGE_KEY, STORAGE_VERSION
from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.hub.websocket import RETRY_TIMER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

DEFAULT_CONFIG_ENTRY_ID = "1"
DEFAULT_HOST = "1.2.3.4"
DEFAULT_PORT = 1234
DEFAULT_SITE = "site_id"

CONTROLLER_HOST = {
    "hostname": "controller_host",
    "ip": DEFAULT_HOST,
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "10:00:00:00:00:01",
    "name": "Controller host",
    "oui": "Producer",
    "sw_mac": "00:00:00:00:01:01",
    "sw_port": 1,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
    "uptime": 1562600160,
}

type ConfigEntryFactoryType = Callable[[], Coroutine[Any, Any, MockConfigEntry]]


class WebsocketMessageMock(Protocol):
    """Fixture to mock websocket message."""

    def __call__(
        self,
        *,
        message: MessageKey | None = None,
        data: list[dict[str, Any]] | dict[str, Any] | None = None,
    ) -> None:
        """Send websocket message."""


@pytest.fixture(autouse=True, name="mock_discovery")
def fixture_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow._async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture(name="mock_device_registry")
def fixture_device_registry(hass: HomeAssistant, device_registry: dr.DeviceRegistry):
    """Mock device registry."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate(
        (
            "00:00:00:00:00:01",
            "00:00:00:00:00:02",
            "00:00:00:00:00:03",
            "00:00:00:00:00:04",
            "00:00:00:00:00:05",
            "00:00:00:00:00:06",
            "00:00:00:00:01:01",
            "00:00:00:00:02:02",
        )
    ):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )


# Config entry fixtures


@pytest.fixture(name="config_entry")
def fixture_config_entry(
    hass: HomeAssistant,
    config_entry_data: MappingProxyType[str, Any],
    config_entry_options: MappingProxyType[str, Any],
) -> MockConfigEntry:
    """Define a config entry fixture."""
    config_entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        entry_id="1",
        unique_id="1",
        data=config_entry_data,
        options=config_entry_options,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="config_entry_data")
def fixture_config_entry_data() -> MappingProxyType[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_HOST: DEFAULT_HOST,
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: DEFAULT_PORT,
        CONF_SITE_ID: DEFAULT_SITE,
        CONF_VERIFY_SSL: False,
    }


@pytest.fixture(name="config_entry_options")
def fixture_config_entry_options() -> MappingProxyType[str, Any]:
    """Define a config entry options fixture."""
    return {}


# Known wireless clients


@pytest.fixture(name="known_wireless_clients")
def fixture_known_wireless_clients() -> list[str]:
    """Known previously observed wireless clients."""
    return []


@pytest.fixture(autouse=True, name="mock_wireless_client_storage")
def fixture_wireless_client_storage(
    hass_storage: dict[str, Any], known_wireless_clients: list[str]
):
    """Mock the known wireless storage."""
    data: dict[str, list[str]] = (
        {"wireless_clients": known_wireless_clients} if known_wireless_clients else {}
    )
    hass_storage[STORAGE_KEY] = {"version": STORAGE_VERSION, "data": data}


# UniFi request mocks


@pytest.fixture(name="mock_requests")
def fixture_request(
    aioclient_mock: AiohttpClientMocker,
    client_payload: list[dict[str, Any]],
    clients_all_payload: list[dict[str, Any]],
    device_payload: list[dict[str, Any]],
    dpi_app_payload: list[dict[str, Any]],
    dpi_group_payload: list[dict[str, Any]],
    firewall_policy_payload: list[dict[str, Any]],
    port_forward_payload: list[dict[str, Any]],
    traffic_rule_payload: list[dict[str, Any]],
    traffic_route_payload: list[dict[str, Any]],
    site_payload: list[dict[str, Any]],
    system_information_payload: list[dict[str, Any]],
    wlan_payload: list[dict[str, Any]],
) -> Callable[[str], None]:
    """Mock default UniFi requests responses."""

    def __mock_requests(host: str = DEFAULT_HOST, site_id: str = DEFAULT_SITE) -> None:
        url = f"https://{host}:{DEFAULT_PORT}"

        def mock_get_request(path: str, payload: list[dict[str, Any]]) -> None:
            # APIV2 request respoonses have `meta` and `data` automatically appended
            json = {}
            if path.startswith("/v2"):
                json = payload
            else:
                json = {"meta": {"rc": "OK"}, "data": payload}

            aioclient_mock.get(
                f"{url}{path}",
                json=json,
                headers={"content-type": CONTENT_TYPE_JSON},
            )

        aioclient_mock.get(url, status=302)  # UniFI OS check
        aioclient_mock.post(
            f"{url}/api/login",
            json={"data": "login successful", "meta": {"rc": "ok"}},
            headers={"content-type": CONTENT_TYPE_JSON},
        )

        mock_get_request("/api/self/sites", site_payload)
        mock_get_request(f"/api/s/{site_id}/stat/sta", client_payload)
        mock_get_request(f"/api/s/{site_id}/rest/user", clients_all_payload)
        mock_get_request(f"/api/s/{site_id}/stat/device", device_payload)
        mock_get_request(f"/api/s/{site_id}/rest/dpiapp", dpi_app_payload)
        mock_get_request(f"/api/s/{site_id}/rest/dpigroup", dpi_group_payload)
        mock_get_request(
            f"/v2/api/site/{site_id}/firewall-policies", firewall_policy_payload
        )
        mock_get_request(f"/api/s/{site_id}/rest/portforward", port_forward_payload)
        mock_get_request(f"/api/s/{site_id}/stat/sysinfo", system_information_payload)
        mock_get_request(f"/api/s/{site_id}/rest/wlanconf", wlan_payload)
        mock_get_request(f"/v2/api/site/{site_id}/trafficrules", traffic_rule_payload)
        mock_get_request(f"/v2/api/site/{site_id}/trafficroutes", traffic_route_payload)

    return __mock_requests


# Request payload fixtures


@pytest.fixture(name="client_payload")
def fixture_client_data() -> list[dict[str, Any]]:
    """Client data."""
    return []


@pytest.fixture(name="clients_all_payload")
def fixture_clients_all_data() -> list[dict[str, Any]]:
    """Clients all data."""
    return []


@pytest.fixture(name="device_payload")
def fixture_device_data() -> list[dict[str, Any]]:
    """Device data."""
    return []


@pytest.fixture(name="dpi_app_payload")
def fixture_dpi_app_data() -> list[dict[str, Any]]:
    """DPI app data."""
    return []


@pytest.fixture(name="dpi_group_payload")
def fixture_dpi_group_data() -> list[dict[str, Any]]:
    """DPI group data."""
    return []


@pytest.fixture(name="firewall_policy_payload")
def firewall_policy_payload_data() -> list[dict[str, Any]]:
    """Firewall policy data."""
    return []


@pytest.fixture(name="port_forward_payload")
def fixture_port_forward_data() -> list[dict[str, Any]]:
    """Port forward data."""
    return []


@pytest.fixture(name="site_payload")
def fixture_site_data() -> list[dict[str, Any]]:
    """Site data."""
    return [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}]


@pytest.fixture(name="system_information_payload")
def fixture_system_information_data() -> list[dict[str, Any]]:
    """System information data."""
    return [
        {
            "anonymous_controller_id": "24f81231-a456-4c32-abcd-f5612345385f",
            "build": "atag_7.4.162_21057",
            "console_display_version": "3.1.15",
            "hostname": "UDMP",
            "name": "UDMP",
            "previous_version": "7.4.156",
            "timezone": "Europe/Stockholm",
            "ubnt_device_type": "UDMPRO",
            "udm_version": "3.0.20.9281",
            "update_available": False,
            "update_downloaded": False,
            "uptime": 1196290,
            "version": "7.4.162",
        }
    ]


@pytest.fixture(name="traffic_rule_payload")
def traffic_rule_payload_data() -> list[dict[str, Any]]:
    """Traffic rule data."""
    return []


@pytest.fixture(name="traffic_route_payload")
def traffic_route_payload_data() -> list[dict[str, Any]]:
    """Traffic route data."""
    return []


@pytest.fixture(name="wlan_payload")
def fixture_wlan_data() -> list[dict[str, Any]]:
    """WLAN data."""
    return []


@pytest.fixture(name="mock_default_requests")
def fixture_default_requests(
    mock_requests: Callable[[str, str], None],
) -> None:
    """Mock UniFi requests responses with default host and site."""
    mock_requests(DEFAULT_HOST, DEFAULT_SITE)


@pytest.fixture(name="config_entry_factory")
async def fixture_config_entry_factory(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> ConfigEntryFactoryType:
    """Fixture factory that can set up UniFi network integration."""

    async def __mock_setup_config_entry() -> MockConfigEntry:
        mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return __mock_setup_config_entry


@pytest.fixture(name="config_entry_setup")
async def fixture_config_entry_setup(
    config_entry_factory: ConfigEntryFactoryType,
) -> MockConfigEntry:
    """Fixture providing a set up instance of UniFi network integration."""
    return await config_entry_factory()


# Websocket fixtures


class WebsocketStateManager(asyncio.Event):
    """Keep an async event that simules websocket context manager.

    Prepares disconnect and reconnect flows.
    """

    def __init__(
        self, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
    ) -> None:
        """Store hass object and initialize asyncio.Event."""
        self.hass = hass
        self.aioclient_mock = aioclient_mock
        super().__init__()

    async def waiter(self, input: Callable[[bytes], None]) -> None:
        """Consume message_handler new_data callback."""
        await self.wait()

    async def disconnect(self) -> None:
        """Mark future as done to make 'await self.api.start_websocket' return."""
        self.set()
        await self.hass.async_block_till_done()

    async def reconnect(self, fail: bool = False) -> None:
        """Set up new future to make 'await self.api.start_websocket' block.

        Mock api calls done by 'await self.api.login'.
        Fail will make 'await self.api.start_websocket' return immediately.
        """
        # Check UniFi OS
        self.aioclient_mock.get(f"https://{DEFAULT_HOST}:1234", status=302)
        self.aioclient_mock.post(
            f"https://{DEFAULT_HOST}:1234/api/login",
            json={"data": "login successful", "meta": {"rc": "ok"}},
            headers={"content-type": CONTENT_TYPE_JSON},
        )

        if not fail:
            self.clear()
        new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
        async_fire_time_changed(self.hass, new_time)
        await self.hass.async_block_till_done()


@pytest.fixture(autouse=True, name="_mock_websocket")
def fixture_aiounifi_websocket_method() -> Generator[AsyncMock]:
    """Mock aiounifi websocket context manager."""
    with patch("aiounifi.controller.Connectivity.websocket") as ws_mock:
        yield ws_mock


@pytest.fixture(autouse=True, name="mock_websocket_state")
def fixture_aiounifi_websocket_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, _mock_websocket: AsyncMock
) -> WebsocketStateManager:
    """Provide a state manager for UniFi websocket."""
    websocket_state_manager = WebsocketStateManager(hass, aioclient_mock)
    _mock_websocket.side_effect = websocket_state_manager.waiter
    return websocket_state_manager


@pytest.fixture(name="mock_websocket_message")
def fixture_aiounifi_websocket_message(
    _mock_websocket: AsyncMock,
) -> WebsocketMessageMock:
    """No real websocket allowed."""

    def make_websocket_call(
        *,
        message: MessageKey | None = None,
        data: list[dict[str, Any]] | dict[str, Any] | None = None,
    ) -> None:
        """Generate a websocket call."""
        message_handler = _mock_websocket.call_args[0][0]

        if data and not message:
            message_handler(orjson.dumps(data))
        elif data and message:
            if not isinstance(data, list):
                data = [data]
            message_handler(
                orjson.dumps({"meta": {"message": message.value}, "data": data})
            )
        else:
            raise NotImplementedError

    return make_websocket_call
