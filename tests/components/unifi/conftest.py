"""Fixtures for UniFi Network methods."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN
from homeassistant.components.unifi.hub.websocket import RETRY_TIMER
from homeassistant.config_entries import ConfigEntry
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
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

DEFAULT_CONFIG_ENTRY_ID = "1"
DEFAULT_HOST = "1.2.3.4"
DEFAULT_PORT = 1234
DEFAULT_SITE = "site_id"


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow._async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture
def mock_device_registry(hass, device_registry: dr.DeviceRegistry):
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
def config_entry_fixture(
    hass: HomeAssistant,
    config_entry_data: MappingProxyType[str, Any],
    config_entry_options: MappingProxyType[str, Any],
) -> ConfigEntry:
    """Define a config entry fixture."""
    config_entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        entry_id="1",
        unique_id="1",
        data=config_entry_data,
        options=config_entry_options,
        version=1,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> MappingProxyType[str, Any]:
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
def config_entry_options_fixture() -> MappingProxyType[str, Any]:
    """Define a config entry options fixture."""
    return {}


@pytest.fixture(name="mock_unifi_requests")
def default_request_fixture(
    aioclient_mock: AiohttpClientMocker,
    client_payload: list[dict[str, Any]],
    clients_all_payload: list[dict[str, Any]],
    device_payload: list[dict[str, Any]],
    dpi_app_payload: list[dict[str, Any]],
    dpi_group_payload: list[dict[str, Any]],
    port_forward_payload: list[dict[str, Any]],
    site_payload: list[dict[str, Any]],
    system_information_payload: list[dict[str, Any]],
    wlan_payload: list[dict[str, Any]],
) -> Callable[[str], None]:
    """Mock default UniFi requests responses."""

    def __mock_default_requests(host: str, site_id: str) -> None:
        url = f"https://{host}:{DEFAULT_PORT}"

        def mock_get_request(path: str, payload: list[dict[str, Any]]) -> None:
            aioclient_mock.get(
                f"{url}{path}",
                json={"meta": {"rc": "OK"}, "data": payload},
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
        mock_get_request(f"/api/s/{site_id}/rest/portforward", port_forward_payload)
        mock_get_request(f"/api/s/{site_id}/stat/sysinfo", system_information_payload)
        mock_get_request(f"/api/s/{site_id}/rest/wlanconf", wlan_payload)

    return __mock_default_requests


# Request payload fixtures


@pytest.fixture(name="client_payload")
def client_data_fixture() -> list[dict[str, Any]]:
    """Client data."""
    return []


@pytest.fixture(name="clients_all_payload")
def clients_all_data_fixture() -> list[dict[str, Any]]:
    """Clients all data."""
    return []


@pytest.fixture(name="device_payload")
def device_data_fixture() -> list[dict[str, Any]]:
    """Device data."""
    return []


@pytest.fixture(name="dpi_app_payload")
def dpi_app_data_fixture() -> list[dict[str, Any]]:
    """DPI app data."""
    return []


@pytest.fixture(name="dpi_group_payload")
def dpi_group_data_fixture() -> list[dict[str, Any]]:
    """DPI group data."""
    return []


@pytest.fixture(name="port_forward_payload")
def port_forward_data_fixture() -> list[dict[str, Any]]:
    """Port forward data."""
    return []


@pytest.fixture(name="site_payload")
def site_data_fixture() -> list[dict[str, Any]]:
    """Site data."""
    return [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}]


@pytest.fixture(name="system_information_payload")
def system_information_data_fixture() -> list[dict[str, Any]]:
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


@pytest.fixture(name="wlan_payload")
def wlan_data_fixture() -> list[dict[str, Any]]:
    """WLAN data."""
    return []


@pytest.fixture(name="setup_default_unifi_requests")
def default_vapix_requests_fixture(
    config_entry: ConfigEntry,
    mock_unifi_requests: Callable[[str, str], None],
) -> None:
    """Mock default UniFi requests responses."""
    mock_unifi_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])


@pytest.fixture(name="prepare_config_entry")
async def prep_config_entry_fixture(
    hass: HomeAssistant, config_entry: ConfigEntry, setup_default_unifi_requests: None
) -> Callable[[], ConfigEntry]:
    """Fixture factory to set up UniFi network integration."""

    async def __mock_setup_config_entry() -> ConfigEntry:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return __mock_setup_config_entry


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, prepare_config_entry: Callable[[], ConfigEntry]
) -> ConfigEntry:
    """Fixture to set up UniFi network integration."""
    return await prepare_config_entry()


# Websocket fixtures


class WebsocketStateManager(asyncio.Event):
    """Keep an async event that simules websocket context manager.

    Prepares disconnect and reconnect flows.
    """

    def __init__(self, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
        """Store hass object and initialize asyncio.Event."""
        self.hass = hass
        self.aioclient_mock = aioclient_mock
        super().__init__()

    async def disconnect(self):
        """Mark future as done to make 'await self.api.start_websocket' return."""
        self.set()
        await self.hass.async_block_till_done()

    async def reconnect(self, fail=False):
        """Set up new future to make 'await self.api.start_websocket' block.

        Mock api calls done by 'await self.api.login'.
        Fail will make 'await self.api.start_websocket' return immediately.
        """
        hub = self.hass.config_entries.async_get_entry(
            DEFAULT_CONFIG_ENTRY_ID
        ).runtime_data
        self.aioclient_mock.get(
            f"https://{hub.config.host}:1234", status=302
        )  # Check UniFi OS
        self.aioclient_mock.post(
            f"https://{hub.config.host}:1234/api/login",
            json={"data": "login successful", "meta": {"rc": "ok"}},
            headers={"content-type": CONTENT_TYPE_JSON},
        )

        if not fail:
            self.clear()
        new_time = dt_util.utcnow() + timedelta(seconds=RETRY_TIMER)
        async_fire_time_changed(self.hass, new_time)
        await self.hass.async_block_till_done()


@pytest.fixture(autouse=True)
def websocket_mock(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Mock 'await self.api.start_websocket' in 'UniFiController.start_websocket'."""
    websocket_state_manager = WebsocketStateManager(hass, aioclient_mock)
    with patch("aiounifi.Controller.start_websocket") as ws_mock:
        ws_mock.side_effect = websocket_state_manager.wait
        yield websocket_state_manager


@pytest.fixture(autouse=True)
def mock_unifi_websocket(hass):
    """No real websocket allowed."""

    def make_websocket_call(
        *,
        message: MessageKey | None = None,
        data: list[dict] | dict | None = None,
    ):
        """Generate a websocket call."""
        hub = hass.config_entries.async_get_entry(DEFAULT_CONFIG_ENTRY_ID).runtime_data
        if data and not message:
            hub.api.messages.handler(data)
        elif data and message:
            if not isinstance(data, list):
                data = [data]
            hub.api.messages.handler(
                {
                    "meta": {"message": message.value},
                    "data": data,
                }
            )
        else:
            raise NotImplementedError

    return make_websocket_call
