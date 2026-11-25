"""Test UniFi Network integration setup process."""

from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from pytest_homeassistant.common import MockConfigEntry, flush_store
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components import unifi
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN,
)
from homeassistant.components.unifi.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.update import ATTR_INSTALLED_VERSION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    STATE_UNKNOWN,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    DEFAULT_CONFIG_ENTRY_ID,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
)
from .test_sensor import FIREWALL_POLICY


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

ADOPTED_DEVICE = {
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
}

PENDING_DEVICE = {
    "adopted": False,
    "board_rev": 3,
    "device_id": "mock-id-pending",
    "ip": "10.0.1.2",
    "mac": PENDING_MAC,
    "model": "US16P150",
    "next_interval": 20,
    "state": 2,
    "type": "usw",
    "version": "4.0.42.10433",
}

# A device may not report its port table until it is adopted
ADOPTED_PENDING_DEVICE = {
    **PENDING_DEVICE,
    "adopted": True,
    "name": "Device 2",
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
    "state": 1,
}

DEVICE_WITH_CHILDREN = {
    **ADOPTED_PENDING_DEVICE,
    "outlet_table": [
        {
            "index": 1,
            "name": "Outlet 1",
            "has_relay": False,
            "has_metering": False,
        }
    ],
}

# Entities of a device loaded by default, disabled by the user in the test below
DISABLED_ENTITIES = (
    (Platform.UPDATE, f"device_update-{ADOPTED_MAC}"),
    (Platform.DEVICE_TRACKER, ADOPTED_MAC),
    (Platform.BUTTON, f"device_restart-{ADOPTED_MAC}"),
    (Platform.SENSOR, f"device_uptime-{ADOPTED_MAC}"),
    (Platform.SENSOR, f"device_state-{ADOPTED_MAC}"),
)


@pytest.mark.parametrize("device_payload", [[DEVICE_WITH_CHILDREN]])
async def test_child_devices_and_entity_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Create child devices and move existing enabled and disabled entities."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, PENDING_MAC)},
    )
    button = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"power_cycle-{PENDING_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="custom_power_cycle",
    )
    sensor = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"poe_power-{PENDING_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        disabled_by=er.RegistryEntryDisabler.USER,
        suggested_object_id="custom_power",
    )
    entity_registry.async_update_entity(button.entity_id, name="Custom power cycle")

    await config_entry_factory()

    port = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"port-{PENDING_MAC}_1"), config_entry.entry_id
    )
    outlet = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"outlet-{PENDING_MAC}_1"), config_entry.entry_id
    )
    assert port is not None
    assert outlet is None
    assert port.parent_device_id == parent.id
    assert port.name == "Port 1"

    migrated_button = entity_registry.async_get(button.entity_id)
    assert migrated_button is not None
    assert migrated_button.device_id == port.id
    assert migrated_button.name == "Custom power cycle"
    assert hass.states.get(button.entity_id) is not None
    migrated_sensor = entity_registry.async_get(sensor.entity_id)
    assert migrated_sensor is not None
    assert migrated_sensor.device_id == port.id
    assert migrated_sensor.disabled_by is er.RegistryEntryDisabler.USER


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                **ADOPTED_DEVICE,
                "outlet_overrides": [
                    {"index": 1, "name": "Outlet 1", "relay_state": True}
                ],
                "outlet_table": [
                    {
                        "index": 1,
                        "name": "Outlet 1",
                        "has_relay": True,
                        "has_metering": True,
                        "relay_state": True,
                        "outlet_power": 42,
                    }
                ],
            }
        ]
    ],
)
async def test_outlet_entities_move_to_child_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Move existing outlet controls and measurements to the same child."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, ADOPTED_MAC)},
    )
    switch = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"outlet-{ADOPTED_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="custom_outlet",
    )
    sensor = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"outlet_power-{ADOPTED_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="custom_outlet_power",
    )

    await config_entry_factory()

    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"outlet-{ADOPTED_MAC}_1"), config_entry.entry_id
    )
    assert child is not None
    assert child.parent_device_id == parent.id
    assert entity_registry.async_get(switch.entity_id).device_id == child.id
    assert entity_registry.async_get(sensor.entity_id).device_id == child.id

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/site_id/rest/device/{ADOPTED_DEVICE['device_id']}",
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.DEVICE_ID: parent.id},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "outlet_overrides": [{"index": 1, "name": "Outlet 1", "relay_state": False}]
    }


@pytest.mark.parametrize(
    ("device_payload", "expected_name"),
    [
        pytest.param(
            [
                {
                    **ADOPTED_DEVICE,
                    "outlet_table": [
                        {
                            "index": 7,
                            "name": "",
                            "has_relay": True,
                            "has_metering": True,
                            "relay_state": True,
                            "outlet_power": 42,
                        }
                    ],
                }
            ],
            "Outlet 7",
            id="empty-name",
        ),
        pytest.param(
            [
                {
                    **ADOPTED_DEVICE,
                    "outlet_table": [
                        {
                            "index": 7,
                            "name": "Desk",
                            "has_relay": True,
                            "has_metering": True,
                            "relay_state": True,
                            "outlet_power": 42,
                        }
                    ],
                }
            ],
            "Desk",
            id="named-outlet",
        ),
    ],
)
async def test_outlet_child_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    expected_name: str,
) -> None:
    """Name an unnamed outlet by its index while preserving reported names."""
    config_entry = await config_entry_factory()
    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"outlet-{ADOPTED_MAC}_7"), config_entry.entry_id
    )
    assert child is not None
    assert child.name == expected_name

    switch_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"outlet-{ADOPTED_MAC}_7"
    )
    sensor_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"outlet_power-{ADOPTED_MAC}_7"
    )
    assert switch_id is not None
    assert sensor_id is not None
    assert entity_registry.async_get(switch_id).device_id == child.id
    assert entity_registry.async_get(sensor_id).device_id == child.id
    assert hass.states.get(switch_id).attributes[ATTR_FRIENDLY_NAME] == expected_name
    assert (
        hass.states.get(sensor_id).attributes[ATTR_FRIENDLY_NAME]
        == f"{expected_name} Outlet power"
    )


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                **ADOPTED_DEVICE,
                "port_table": [
                    {
                        "port_idx": 1,
                        "name": "Port 1",
                        "port_poe": True,
                        "poe_enable": True,
                    }
                ],
                "outlet_table": [
                    {
                        "index": 1,
                        "name": "Outlet 1",
                        "has_relay": True,
                        "has_metering": False,
                        "relay_state": True,
                    }
                ],
            }
        ]
    ],
)
async def test_child_devices_retained_on_device_updates(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Keep children when updated device data is incomplete or renamed."""
    config_entry = await config_entry_factory()
    updated = device_payload[0]

    port = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"port-{ADOPTED_MAC}_1"), config_entry.entry_id
    )
    outlet = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"outlet-{ADOPTED_MAC}_1"), config_entry.entry_id
    )
    assert port is not None
    assert outlet is not None
    assert port.name == "Port 1"
    assert outlet.name == "Outlet 1"
    button_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"power_cycle-{ADOPTED_MAC}_1"
    )
    assert button_id is not None
    assert entity_registry.async_get(button_id).device_id == port.id
    assert hass.states.get(button_id) is not None

    parent = device_registry.async_get(port.parent_device_id)
    assert isinstance(parent, dr.DeviceEntry)
    assert parent.hw_version == "3"
    incomplete = updated.copy()
    incomplete.pop("board_rev")
    mock_websocket_message(message=MessageKey.DEVICE, data=incomplete)
    await hass.async_block_till_done()
    parent = device_registry.async_get(parent.id)
    assert isinstance(parent, dr.DeviceEntry)
    assert parent.hw_version == "3"

    mock_websocket_message(
        message=MessageKey.DEVICE,
        data={
            **updated,
            "port_table": [
                {"port_idx": 1, "name": "Office", "port_poe": True, "poe_enable": True}
            ],
            "outlet_table": [
                {
                    "index": 1,
                    "name": "Desk",
                    "has_relay": True,
                    "has_metering": False,
                    "relay_state": True,
                }
            ],
        },
    )
    await hass.async_block_till_done()
    assert device_registry.async_get(port.id).name == "Port 1"
    assert device_registry.async_get(outlet.id).name == "Outlet 1"

    mock_websocket_message(message=MessageKey.DEVICE, data=ADOPTED_DEVICE)
    await hass.async_block_till_done()
    assert device_registry.async_get(port.id)
    assert device_registry.async_get(outlet.id)


@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "readonly", "_id": "1"}]],
)
@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                **ADOPTED_DEVICE,
                "port_table": [{"port_idx": 1, "name": "Port 1", "port_poe": False}],
                "outlet_table": [
                    {
                        "index": 1,
                        "name": "Outlet 1",
                        "has_relay": False,
                        "has_metering": False,
                    }
                ],
            }
        ]
    ],
)
async def test_no_child_devices_without_entities(
    device_registry: dr.DeviceRegistry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Do not create children when no entities are eligible."""
    config_entry = await config_entry_factory()
    for kind in ("port", "outlet"):
        assert not device_registry.async_get_child_device_by_identifier(
            (DOMAIN, f"{kind}-{ADOPTED_MAC}_1"), config_entry.entry_id
        )


@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "readonly", "_id": "1"}]],
)
@pytest.mark.parametrize("device_payload", [[ADOPTED_PENDING_DEVICE]])
async def test_migrate_entities_when_they_become_eligible(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Move an entity once its option permits it to be loaded."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, PENDING_MAC)},
    )
    button = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"power_cycle-{PENDING_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    sensor = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"port_rx-{PENDING_MAC}_1",
        config_entry=config_entry,
        device_id=parent.id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await config_entry_factory()

    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"port-{PENDING_MAC}_1"), config_entry.entry_id
    )
    assert child is not None
    assert entity_registry.async_get(button.entity_id).device_id == parent.id
    assert entity_registry.async_get(sensor.entity_id).device_id == parent.id
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_BANDWIDTH_SENSORS: True}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(button.entity_id).device_id == parent.id
    assert entity_registry.async_get(sensor.entity_id).device_id == child.id
    assert (
        entity_registry.async_get(button.entity_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )
    assert (
        entity_registry.async_get(sensor.entity_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )


@pytest.mark.parametrize("device_payload", [[ADOPTED_DEVICE, PENDING_DEVICE]])
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

    def entity_ids(mac: str) -> list[str | None]:
        return [
            entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
            for platform, unique_id in (
                (Platform.UPDATE, f"device_update-{mac}"),
                (Platform.SWITCH, f"poe-{mac}_1"),
                (Platform.BUTTON, f"power_cycle-{mac}_1"),
                (Platform.SENSOR, f"poe_power-{mac}_1"),
            )
        ]

    # Only the adopted device gets a device entry and entities
    assert device_entry(ADOPTED_MAC)
    assert entity_ids(ADOPTED_MAC)[0]
    assert not device_entry(PENDING_MAC)
    assert not any(entity_ids(PENDING_MAC))
    assert not device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"port-{PENDING_MAC}_1"), config_entry.entry_id
    )

    # Updates of a device still pending adoption change nothing
    mock_websocket_message(
        message=MessageKey.DEVICE, data={**PENDING_DEVICE, "state": 1}
    )
    await hass.async_block_till_done()

    assert not device_entry(PENDING_MAC)
    assert not any(entity_ids(PENDING_MAC))

    # Adopting the device creates its entities, including those of its ports
    # that are first reported in the same update
    mock_websocket_message(message=MessageKey.DEVICE, data=ADOPTED_PENDING_DEVICE)
    await hass.async_block_till_done()

    assert (pending_device_entry := device_entry(PENDING_MAC))
    assert all(entity_ids(PENDING_MAC))
    assert device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"port-{PENDING_MAC}_1"), config_entry.entry_id
    )

    # Forgetting the device in the controller removes its loaded entities,
    # the registry entries of its disabled entities are kept
    mock_websocket_message(message=MessageKey.DEVICE, data=PENDING_DEVICE)
    await hass.async_block_till_done()

    assert [bool(entity_id) for entity_id in entity_ids(PENDING_MAC)] == [
        False,
        True,
        False,
        True,
    ]

    # The device entry of a device that is not adopted can be removed from the UI
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(pending_device_entry.id)
    assert response["success"]
    assert not device_entry(PENDING_MAC)
    assert not any(entity_ids(PENDING_MAC))

    # Adopting the device again recreates everything, including the entities
    # that are disabled by default and were never loaded
    mock_websocket_message(message=MessageKey.DEVICE, data=ADOPTED_PENDING_DEVICE)
    await hass.async_block_till_done()

    assert device_entry(PENDING_MAC)
    assert all(entity_ids(PENDING_MAC))

    # A device adopted from the start that is forgotten and adopted again
    mock_websocket_message(
        message=MessageKey.DEVICE, data={**ADOPTED_DEVICE, "adopted": False}
    )
    await hass.async_block_till_done()

    assert not entity_ids(ADOPTED_MAC)[0]

    mock_websocket_message(message=MessageKey.DEVICE, data=ADOPTED_DEVICE)
    await hass.async_block_till_done()

    assert entity_ids(ADOPTED_MAC)[0]

    # Unloading with a device still pending adoption
    mock_websocket_message(
        message=MessageKey.DEVICE, data={**ADOPTED_DEVICE, "adopted": False}
    )
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("device_payload", [[ADOPTED_DEVICE]])
async def test_device_without_loaded_entities_readopted(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Verify a device is recreated after removal without any loaded entity."""
    for platform, unique_id in DISABLED_ENTITIES:
        entity_registry.async_get_or_create(
            platform,
            DOMAIN,
            unique_id,
            config_entry=config_entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
    await config_entry_factory()

    def device_entry() -> dr.DeviceEntry | None:
        return device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, ADOPTED_MAC), config_entry.entry_id
        )

    def update_entity_id() -> str | None:
        return entity_registry.async_get_entity_id(
            Platform.UPDATE, DOMAIN, f"device_update-{ADOPTED_MAC}"
        )

    assert (entry := device_entry())
    assert all(
        hass.states.get(entity.entity_id) is None
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    )

    # Forgetting the device is not noticed by any entity
    mock_websocket_message(
        message=MessageKey.DEVICE, data={**ADOPTED_DEVICE, "adopted": False}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(entry.id)
    assert response["success"]
    assert not device_entry()
    assert not update_entity_id()

    mock_websocket_message(message=MessageKey.DEVICE, data=ADOPTED_DEVICE)
    await hass.async_block_till_done()

    assert device_entry()
    assert update_entity_id()


@pytest.mark.parametrize("device_payload", [[ADOPTED_PENDING_DEVICE]])
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("switch.device_2_port_1_poe", id="entity_id"),
        pytest.param("switch.device_2_poe", id="renamed_entity_id"),
    ],
)
async def test_disabled_entity_removed_from_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_setup: MockConfigEntry,
    entity_id: str,
) -> None:
    """Verify a disabled entity is recreated once its registry entry is removed.

    A disabled entity is never added, so only the registry tells it is gone.
    """
    entry = entity_registry.async_update_entity(
        "switch.device_2_port_1_poe", new_entity_id=entity_id
    )
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None

    # Any scan for entities recreates it, here the one for updated options,
    # under the ID the registry restores for a deleted entity
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_TRACK_CLIENTS: False}
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_payload", [[ADOPTED_PENDING_DEVICE]])
async def test_entity_not_added_retried(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Verify an entity the platform does not add is tried again on the next scan."""
    entity_id = entity_registry.async_get_or_create(
        Platform.UPDATE,
        DOMAIN,
        f"device_update-{PENDING_MAC}",
        config_entry=config_entry,
        suggested_object_id="device_2_firmware",
    ).entity_id
    # The platform does not add an entity whose entity ID is in use
    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await config_entry_factory()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    hass.states.async_remove(entity_id)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_TRACK_CLIENTS: False}
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get(entity_id).attributes[ATTR_INSTALLED_VERSION]
        == ADOPTED_PENDING_DEVICE["version"]
    )


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
async def test_firewall_policy_entities_move_to_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Move firewall policy entities to a child device of UniFi Network."""
    assert config_entry.unique_id is not None
    network = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(SWITCH_DOMAIN, config_entry.unique_id)},
    )
    switch = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"firewall_policy-{FIREWALL_POLICY['_id']}",
        config_entry=config_entry,
        device_id=network.id,
        suggested_object_id="custom_firewall_policy",
    )

    await config_entry_factory()

    policy_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"firewall_policy-{FIREWALL_POLICY['_id']}"), config_entry.entry_id
    )
    assert policy_device is not None
    assert policy_device.parent_device_id == network.id
    assert policy_device.name == FIREWALL_POLICY["name"]

    migrated_switch = entity_registry.async_get(switch.entity_id)
    assert migrated_switch is not None
    assert migrated_switch.entity_id == "switch.custom_firewall_policy"
    assert migrated_switch.device_id == policy_device.id
    assert hass.states.get(switch.entity_id) is not None
