"""Test UniFi Network integration setup process."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN,
)
from homeassistant.components.unifi.coordinator import POLL_INTERVAL
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.unifi.hub.client_store import SAVE_DELAY, storage_key
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CONFIG_ENTRY_ID,
    NETWORK_API_URL,
    NETWORK_SITE_ID,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    mock_network_api_lists,
)

from tests.common import MockConfigEntry, async_fire_time_changed, flush_store
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


async def test_setup_entry_fails_config_entry_not_ready(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with patch(
        "homeassistant.components.unifi.get_unifi_api",
        side_effect=CannotConnect,
    ):
        config_entry = await config_entry_factory()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_fails_trigger_reauth_flow(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with (
        patch(
            "homeassistant.components.unifi.get_unifi_api",
            side_effect=AuthenticationRequired,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        config_entry = await config_entry_factory()
        mock_flow_init.assert_called_once()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "hostname": "client_1",
                "ip": "10.0.0.1",
                "is_wired": False,
                "mac": "00:00:00:00:00:01",
            },
            {
                "hostname": "client_2",
                "ip": "10.0.0.2",
                "is_wired": False,
                "mac": "00:00:00:00:00:02",
            },
        ]
    ],
)
async def test_wireless_clients(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Verify wireless clients class."""
    hass_storage[unifi.STORAGE_KEY] = {
        "version": unifi.STORAGE_VERSION,
        "data": {
            DEFAULT_CONFIG_ENTRY_ID: {
                "wireless_devices": ["00:00:00:00:00:00", "00:00:00:00:00:01"]
            }
        },
    }

    await config_entry_factory()
    await flush_store(hass.data[unifi.UNIFI_WIRELESS_CLIENTS]._store)

    assert sorted(hass_storage[unifi.STORAGE_KEY]["data"]["wireless_clients"]) == [
        "00:00:00:00:00:00",
        "00:00:00:00:00:01",
        "00:00:00:00:00:02",
    ]


@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "hostname": "Wired client",
                "is_wired": True,
                "mac": "00:00:00:00:00:01",
                "oui": "Producer",
                "wired-rx_bytes": 1234000000,
                "wired-tx_bytes": 5678000000,
                "uptime": 1600094505,
            },
            {
                "is_wired": False,
                "mac": "00:00:00:00:00:02",
                "name": "Wireless client",
                "oui": "Producer",
                "rx_bytes": 2345000000,
                "tx_bytes": 6789000000,
                "uptime": 60,
            },
        ]
    ],
)
@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "has_fan": True,
                "fan_level": 0,
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device 1",
                "next_interval": 20,
                "overheating": True,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
            CONF_TRACK_CLIENTS: True,
            CONF_TRACK_DEVICES: True,
        }
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    client_payload: list[dict[str, Any]],
    device_payload: list[dict[str, Any]],
    mock_websocket_message: WebsocketMessageMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Verify removing a device manually."""
    config_entry = await config_entry_factory()

    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    # Try to remove an active client from UI: allowed
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"]), config_entry.entry_id
    )
    response = await ws_client.remove_device(device_entry.id)
    assert response["success"]
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"]), config_entry.entry_id
    )

    # Try to remove an active device from UI: not allowed
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device_payload[0]["mac"]), config_entry.entry_id
    )
    response = await ws_client.remove_device(device_entry.id)
    assert not response["success"]
    assert device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, device_payload[0]["mac"]), config_entry.entry_id
    )

    # Remove a client from Unifi API
    mock_websocket_message(message=MessageKey.CLIENT_REMOVED, data=[client_payload[1]])
    await hass.async_block_till_done()

    # Try to remove an inactive client from UI: allowed
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, client_payload[1]["mac"]), config_entry.entry_id
    )
    response = await ws_client.remove_device(device_entry.id)
    assert response["success"]
    assert not device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, client_payload[1]["mac"]), config_entry.entry_id
    )


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Test removing an unexpected child device is rejected."""
    config_entry = await config_entry_factory()
    assert await async_setup_component(hass, "config", {})
    parent_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test_parent_device")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "test_child_device")},
        parent_device_id=parent_device.id,
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(child_device.id)
    assert not response["success"]
    assert (
        response["error"]["message"]
        == "Failed to remove device entry, rejected by integration"
    )
    assert device_registry.async_get(child_device.id)


async def test_setup_entry_with_api_key(
    hass: HomeAssistant,
    network_api_config_entry_setup: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an entry set up with an API key loads and polls, without a websocket."""
    config_entry = network_api_config_entry_setup
    hub = config_entry.runtime_data

    assert config_entry.state is ConfigEntryState.LOADED
    assert hub.config.uses_api_key
    assert hub.is_admin
    assert hub.available
    assert hub.websocket.ws_task is None, "the Integration API has no websocket"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, config_entry.unique_id), config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "10.6.106"


async def test_setup_entry_with_rejected_api_key_triggers_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_api_config_entry: MockConfigEntry,
) -> None:
    """Test a rejected API key starts a reauthentication flow."""
    aioclient_mock.get(
        f"{NETWORK_API_URL}/v1/info", status=401, json={"error": {"code": 401}}
    )

    await hass.config_entries.async_setup(network_api_config_entry.entry_id)
    await hass.async_block_till_done()

    assert network_api_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["step_id"] == "reauth_api_key"


@pytest.mark.parametrize(
    ("status", "state", "reauth"),
    [
        (401, ConfigEntryState.SETUP_ERROR, True),
        (503, ConfigEntryState.SETUP_RETRY, False),
    ],
)
async def test_setup_entry_with_api_key_site_request_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_api_config_entry: MockConfigEntry,
    status: int,
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """Test a failing site request after the key was accepted maps like the first."""
    aioclient_mock.get(
        f"{NETWORK_API_URL}/v1/info", json={"applicationVersion": "10.6.106"}
    )
    aioclient_mock.get(
        f"{NETWORK_API_URL}/v1/sites",
        status=status,
        json={"error": {"code": status, "message": "failed"}},
    )

    await hass.config_entries.async_setup(network_api_config_entry.entry_id)
    await hass.async_block_till_done()

    assert network_api_config_entry.state is state
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["step_id"] for flow in flows] == (["reauth_api_key"] if reauth else [])


async def test_revoked_api_key_triggers_reauth_while_polling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    network_api_config_entry_setup: MockConfigEntry,
) -> None:
    """Test a key revoked after setup starts a reauthentication flow from a poll."""
    config_entry = network_api_config_entry_setup
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{NETWORK_API_URL}/v1/sites/{NETWORK_SITE_ID}/clients",
        status=401,
        json={"error": {"code": 401, "message": "Unauthorized"}},
    )
    mock_network_api_lists(aioclient_mock)
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["step_id"] == "reauth_api_key"


@pytest.mark.parametrize(
    "network_client_payload",
    [
        [
            {
                "type": "WIRED",
                "id": "f9edef13-b667-369f-9556-bc36978095af",
                "name": "ha",
                "macAddress": "00:00:00:00:00:01",
                "access": {"type": "DEFAULT"},
            }
        ]
    ],
)
async def test_remove_entry_with_api_key_deletes_stored_clients(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    network_api_config_entry_setup: MockConfigEntry,
) -> None:
    """Test removing an entry set up with an API key deletes its stored clients."""
    config_entry = network_api_config_entry_setup
    key = storage_key(config_entry)
    hub = config_entry.runtime_data
    assert hub.network_clients is not None
    await flush_store(hub.network_clients._store)
    assert key in hass_storage

    # A poll leaves a delayed save pending when the entry goes
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert key not in hass_storage

    freezer.tick(timedelta(seconds=SAVE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert key not in hass_storage, "the pending save did not put the file back"
