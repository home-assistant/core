"""Test UniFi Network integration setup process."""

from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest

from homeassistant.components import unifi
from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_SITE_ID,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CONFIG_ENTRY_ID,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
)

from tests.common import MockConfigEntry, flush_store
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


async def test_migrate_legacy_entry_preserves_track_clients_default(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Legacy entries keep tracking clients enabled after migration."""
    config_entry = await config_entry_factory()

    assert config_entry.minor_version == 2
    assert config_entry.options[CONF_TRACK_CLIENTS] is True


@pytest.mark.parametrize("config_entry_options", [{CONF_TRACK_CLIENTS: False}])
async def test_migrate_legacy_entry_preserves_explicit_track_clients_false(
    hass: HomeAssistant, config_entry_factory: ConfigEntryFactoryType
) -> None:
    """Legacy entries keep an explicit disabled client tracking option."""
    config_entry = await config_entry_factory()

    assert config_entry.minor_version == 2
    assert config_entry.options[CONF_TRACK_CLIENTS] is False


@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "hostname": "client_1",
                "ip": "10.0.0.1",
                "is_wired": False,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:01",
            }
        ]
    ],
)
async def test_new_entry_defaults_track_clients_off(
    hass: HomeAssistant,
    config_entry_data: dict[str, Any],
    mock_requests,
) -> None:
    """New entries should not create client trackers by default."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=DEFAULT_CONFIG_ENTRY_ID,
        unique_id="1",
        data=config_entry_data,
        options={},
        minor_version=2,
    )
    config_entry.add_to_hass(hass)

    mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}
    assert hass.states.async_entity_ids(TRACKER_DOMAIN) == []


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
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])}
    )
    response = await ws_client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]
    assert not device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[0]["mac"])}
    )

    # Try to remove an active device from UI: not allowed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device_payload[0]["mac"])}
    )
    response = await ws_client.remove_device(device_entry.id, config_entry.entry_id)
    assert not response["success"]
    assert device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, device_payload[0]["mac"])}
    )

    # Remove a client from Unifi API
    mock_websocket_message(message=MessageKey.CLIENT_REMOVED, data=[client_payload[1]])
    await hass.async_block_till_done()

    # Try to remove an inactive client from UI: allowed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[1]["mac"])}
    )
    response = await ws_client.remove_device(device_entry.id, config_entry.entry_id)
    assert response["success"]
    assert not device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, client_payload[1]["mac"])}
    )
