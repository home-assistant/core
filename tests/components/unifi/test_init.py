"""Test UniFi Network integration setup process."""

from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components import unifi
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CONFIG_ENTRY_ID,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
)

from tests.common import flush_store
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


ADOPTED_MAC = "00:00:00:00:01:01"
PENDING_MAC = "00:00:00:00:01:02"

PENDING_DEVICE = {
    "adopted": False,
    "board_rev": 3,
    "device_id": "mock-id-pending",
    "ip": "10.0.1.2",
    "mac": PENDING_MAC,
    "model": "US16P150",
    "next_interval": 20,
    "port_table": [
        {
            "media": "GE",
            "name": "Port 1",
            "port_idx": 1,
            "poe_enable": True,
            "poe_mode": "auto",
            "port_poe": True,
            "up": True,
        }
    ],
    "state": 2,
    "type": "usw",
    "version": "4.0.42.10433",
}


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "adopted": True,
                "board_rev": 3,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": ADOPTED_MAC,
                "model": "US16P150",
                "name": "Device 1",
                "next_interval": 20,
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            },
            PENDING_DEVICE,
        ]
    ],
)
async def test_device_pending_adoption(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Verify devices only get entities while adopted by the controller."""
    config_entry = await config_entry_factory()

    def device_entry(mac: str) -> dr.DeviceEntry | None:
        return device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), config_entry.entry_id
        )

    def update_entity_id(mac: str) -> str | None:
        return entity_registry.async_get_entity_id(
            Platform.UPDATE, DOMAIN, f"device_update-{mac}"
        )

    def poe_entity_id(mac: str) -> str | None:
        return entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, f"poe-{mac}_1"
        )

    # Only the adopted device gets a device entry and entities
    assert device_entry(ADOPTED_MAC)
    assert update_entity_id(ADOPTED_MAC)
    assert not device_entry(PENDING_MAC)
    assert not update_entity_id(PENDING_MAC)
    assert not poe_entity_id(PENDING_MAC)

    # Adopting the device creates its entities, including those of its ports
    mock_websocket_message(
        message=MessageKey.DEVICE,
        data={**PENDING_DEVICE, "adopted": True, "name": "Device 2", "state": 1},
    )
    await hass.async_block_till_done()

    assert (pending_device_entry := device_entry(PENDING_MAC))
    assert update_entity_id(PENDING_MAC)
    assert poe_entity_id(PENDING_MAC)

    # Forgetting the device in the controller removes its loaded entities again
    mock_websocket_message(message=MessageKey.DEVICE, data=PENDING_DEVICE)
    await hass.async_block_till_done()

    assert not update_entity_id(PENDING_MAC)

    # The device entry of a device that is not adopted can be removed from the UI
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(pending_device_entry.id)
    assert response["success"]
    assert not device_entry(PENDING_MAC)
