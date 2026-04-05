"""Tests for the Connectivity Monitor sensor platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.connectivity_monitor.const import (
    AD_DC_PORTS,
    CONF_ALERT_ACTION,
    CONF_ALERT_ACTION_DELAY,
    CONF_ALERT_DELAY,
    CONF_ALERT_GROUP,
    CONF_BLUETOOTH_ADDRESS,
    CONF_DNS_SERVER,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOST,
    CONF_INACTIVE_TIMEOUT,
    CONF_INTERVAL,
    CONF_MATTER_NODE_ID,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TARGETS,
    CONF_ZHA_IEEE,
    DEFAULT_DNS_SERVER,
    DEFAULT_INACTIVE_TIMEOUT,
    DOMAIN,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_ZHA,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)


def _alerting_network_config_entry(
    *,
    alert_delay: int = 2,
    action_delay: int = 3,
) -> MockConfigEntry:
    """Return a network config entry with alert settings enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: "ICMP",
                    "device_name": "Router",
                    CONF_ALERT_GROUP: "family",
                    CONF_ALERT_DELAY: alert_delay,
                    CONF_ALERT_ACTION: "automation.router_recovery",
                    CONF_ALERT_ACTION_DELAY: action_delay,
                }
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )


async def test_network_sensors_expose_expected_state(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test the network sensors created for a simple ICMP target."""
    network_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 8.7,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(network_config_entry.entry_id)
        await hass.async_block_till_done()

    assert network_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.connectivity_monitor_router_icmp")
    assert state is not None
    assert state.state == "Connected"
    assert state.attributes["host"] == "192.168.1.1"
    assert state.attributes["protocol"] == "ICMP"
    assert state.attributes["latency_ms"] == 8.7
    assert state.attributes["resolved_ip"] == "192.168.1.1"
    assert state.attributes["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert state.attributes["icon"] == "mdi:lan-connect"

    overview_state = hass.states.get("sensor.connectivity_monitor_router_overall")
    assert overview_state is not None
    assert overview_state.state == "Connected"
    assert overview_state.attributes["device_name"] == "Router"
    assert overview_state.attributes["monitored_services"] == [
        {
            "protocol": "ICMP",
            "status": "Connected",
            "latency_ms": 8.7,
            "mac_address": "AA:BB:CC:DD:EE:FF",
        }
    ]
    assert overview_state.attributes["icon"] == "mdi:check-network"


async def test_coordinator_refresh_uses_default_data_on_failure(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test refresh failures fall back to the coordinator default result."""
    network_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 5.0,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": None,
                }
            ),
        ) as mock_update_target,
    ):
        assert await hass.config_entries.async_setup(network_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = network_config_entry.runtime_data.coordinator

        mock_update_target.side_effect = OSError("probe failed")
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.connectivity_monitor_router_icmp")
    assert state is not None
    assert state.state == "Disconnected"
    assert state.attributes["icon"] == "mdi:lan-disconnect"

    overview_state = hass.states.get("sensor.connectivity_monitor_router_overall")
    assert overview_state is not None
    assert overview_state.state == "Disconnected"
    assert overview_state.attributes["icon"] == "mdi:close-network"


async def test_zha_sensor_exposes_expected_state_and_attributes(
    hass: HomeAssistant,
) -> None:
    """Test ZHA sensor state, attributes, and icon."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ZigBee Monitor",
        unique_id="connectivity_monitor_zha",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                    CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                    "device_name": "Hallway Sensor",
                }
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    last_seen = datetime.now().timestamp()
    with patch(
        "homeassistant.components.connectivity_monitor.sensor.async_get_zha_device_last_seen",
        AsyncMock(return_value=last_seen),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.connectivity_monitor_zha_hallway_sensor")
    assert state is not None
    assert state.state == "Active"
    assert state.attributes["ieee"] == "00:11:22:33:44:55:66:77"
    assert state.attributes["device_name"] == "Hallway Sensor"
    assert state.attributes["monitor_type"] == "zha"
    assert state.attributes["timeout_minutes"] == 60
    assert state.attributes["last_seen"] is not None
    assert state.attributes["icon"] == "mdi:zigbee"


@pytest.mark.parametrize(
    (
        "protocol",
        "entry_unique_id",
        "target",
        "entity_id",
        "patch_path",
        "patch_value",
        "expected_state",
        "expected_icon",
        "expected_attr_key",
        "expected_attr_value",
    ),
    [
        (
            PROTOCOL_MATTER,
            "connectivity_monitor_matter",
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: "matter:1-1234",
                CONF_MATTER_NODE_ID: "1-1234",
                "device_name": "Thermostat",
            },
            "sensor.connectivity_monitor_matter_thermostat",
            "homeassistant.components.connectivity_monitor.sensor.async_get_matter_device_active",
            True,
            "Active",
            "mdi:chip",
            "node_id",
            "1-1234",
        ),
        (
            PROTOCOL_ESPHOME,
            "connectivity_monitor_esphome",
            {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: "esphome:node-1",
                CONF_ESPHOME_DEVICE_ID: "node-1",
                "device_name": "Garage Node",
            },
            "sensor.connectivity_monitor_esphome_garage_node",
            "homeassistant.components.connectivity_monitor.sensor.async_get_esphome_device_active",
            True,
            "Active",
            "mdi:chip",
            "device_id",
            "node-1",
        ),
        (
            PROTOCOL_BLUETOOTH,
            "connectivity_monitor_bluetooth",
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "device_name": "Tracker",
            },
            "sensor.connectivity_monitor_bluetooth_tracker",
            "homeassistant.components.connectivity_monitor.sensor.async_get_bluetooth_device_details",
            {
                "active": True,
                "device_found": True,
                "rssi": -55,
                "source": "local",
                "connectable": True,
            },
            "Active",
            "mdi:bluetooth",
            "bt_address",
            "AA:BB:CC:DD:EE:FF",
        ),
    ],
)
async def test_protocol_specific_sensors_expose_expected_state(
    hass: HomeAssistant,
    protocol: str,
    entry_unique_id: str,
    target: dict[str, str],
    entity_id: str,
    patch_path: str,
    patch_value: bool | dict[str, object],
    expected_state: str,
    expected_icon: str,
    expected_attr_key: str,
    expected_attr_value: str,
) -> None:
    """Test Matter, ESPHome, and Bluetooth sensor state and attributes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{protocol} Monitor",
        unique_id=entry_unique_id,
        version=2,
        data={
            CONF_TARGETS: [target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    with patch(patch_path, AsyncMock(return_value=patch_value)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[expected_attr_key] == expected_attr_value
    assert state.attributes["device_name"] == target["device_name"]
    assert state.attributes["monitor_type"] == protocol.lower()
    assert state.attributes["icon"] == expected_icon

    if protocol == PROTOCOL_BLUETOOTH:
        assert state.attributes["rssi"] == -55
        assert state.attributes["source"] == "local"
        assert state.attributes["connectable"] is True


@pytest.mark.parametrize(
    ("entry_unique_id", "target", "entity_id", "patch_path", "patch_value"),
    [
        (
            "connectivity_monitor_zha",
            {
                CONF_PROTOCOL: PROTOCOL_ZHA,
                CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                "device_name": "Hallway Sensor",
            },
            "sensor.connectivity_monitor_zha_hallway_sensor",
            "homeassistant.components.connectivity_monitor.sensor."
            "ConnectivityMonitorCoordinator._async_update_data",
            {},
        ),
        (
            "connectivity_monitor_matter",
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: "matter:1-1234",
                CONF_MATTER_NODE_ID: "1-1234",
                "device_name": "Thermostat",
            },
            "sensor.connectivity_monitor_matter_thermostat",
            "homeassistant.components.connectivity_monitor.sensor.async_get_matter_device_active",
            None,
        ),
        (
            "connectivity_monitor_esphome",
            {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: "esphome:node-1",
                CONF_ESPHOME_DEVICE_ID: "node-1",
                "device_name": "Garage Node",
            },
            "sensor.connectivity_monitor_esphome_garage_node",
            "homeassistant.components.connectivity_monitor.sensor.async_get_esphome_device_active",
            None,
        ),
        (
            "connectivity_monitor_bluetooth",
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "device_name": "Tracker",
            },
            "sensor.connectivity_monitor_bluetooth_tracker",
            "homeassistant.components.connectivity_monitor.sensor.async_get_bluetooth_device_details",
            {"active": False, "device_found": False},
        ),
    ],
)
async def test_protocol_specific_sensors_show_unknown_when_device_missing(
    hass: HomeAssistant,
    entry_unique_id: str,
    target: dict[str, str],
    entity_id: str,
    patch_path: str,
    patch_value: object,
) -> None:
    """Test ZHA, Matter, ESPHome, and Bluetooth show Unknown when device data is absent."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Typed Monitor",
        unique_id=entry_unique_id,
        version=2,
        data={
            CONF_TARGETS: [target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    with patch(patch_path, AsyncMock(return_value=patch_value)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Unknown"


async def test_alert_handler_triggers_notification_and_action_after_delays(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test delayed notification and action alerts for a network overview sensor."""
    entry = _alerting_network_config_entry(alert_delay=2, action_delay=3)
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 5.0,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.connectivity_monitor_router_overall"
    hass.states.async_set(entity_id, "Disconnected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 0
    assert len(alert_events) == 0

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert notify_calls[0].data["message"] == (
        "❌ Device Router (192.168.1.1) has been disconnected for 2 minutes"
    )
    assert len(alert_events) == 0

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1
    assert alert_events[0].data["action_entity_id"] == "automation.router_recovery"
    assert alert_events[0].data["device_name"] == "Router"
    assert alert_events[0].data["device_address"] == "192.168.1.1"
    assert alert_events[0].data["minutes_offline"] == 3


async def test_alert_handler_sends_recovery_after_confirmed_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test recovery notification and recovery action after the device stays recovered."""
    entry = _alerting_network_config_entry(alert_delay=1, action_delay=1)
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 5.0,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.connectivity_monitor_router_overall"
    hass.states.async_set(entity_id, "Disconnected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1

    hass.states.async_set(entity_id, "Connected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify_calls) == 2
    assert notify_calls[1].data["message"] == (
        "✅ Device Router (192.168.1.1) has recovered and is now connected"
    )
    assert len(alert_events) == 2
    assert alert_events[1].data["action_entity_id"] == "automation.router_recovery"
    assert alert_events[1].data["recovered"] is True


async def test_alert_handler_cancels_recovery_when_device_flaps(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a brief reconnect does not emit recovery alerts if the device drops again."""
    entry = _alerting_network_config_entry(alert_delay=2, action_delay=2)
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 5.0,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.connectivity_monitor_router_overall"
    hass.states.async_set(entity_id, "Disconnected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 0
    assert len(alert_events) == 0

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1

    hass.states.async_set(entity_id, "Connected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, "Disconnected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert notify_calls[0].data["message"] == (
        "❌ Device Router (192.168.1.1) has been disconnected for 2 minutes"
    )
    assert len(alert_events) == 1
    assert "recovered" not in alert_events[0].data


async def test_alert_handler_does_not_repeat_notification_or_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repeated timer checks do not emit duplicate outage side effects."""
    entry = _alerting_network_config_entry(alert_delay=1, action_delay=1)
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 5.0,
                    "resolved_ip": "192.168.1.1",
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.connectivity_monitor_router_overall"
    hass.states.async_set(entity_id, "Disconnected")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert len(alert_events) == 1

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert notify_calls[0].data["message"] == (
        "❌ Device Router (192.168.1.1) has been disconnected for 1 minutes"
    )
    assert len(alert_events) == 1
    assert alert_events[0].data["action_entity_id"] == "automation.router_recovery"
    assert alert_events[0].data["minutes_offline"] == 1


async def test_alert_handler_handles_startup_offline_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an entity already offline at setup still triggers alerts after the delay."""
    entry = _alerting_network_config_entry(alert_delay=1, action_delay=5)
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": False,
                    "latency": None,
                    "resolved_ip": None,
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.connectivity_monitor_router_overall")
        assert state is not None
        assert state.state == "Disconnected"

        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert notify_calls[0].data["message"] == (
        "❌ Device Router (192.168.1.1) has been disconnected for 1 minutes"
    )


def _zha_config_entry(
    *,
    inactive_timeout: int = DEFAULT_INACTIVE_TIMEOUT,
) -> MockConfigEntry:
    """Return a ZHA config entry for a single device."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ZigBee Monitor",
        unique_id="connectivity_monitor_zha",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                    CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                    "device_name": "Back Door Sensor",
                    CONF_INACTIVE_TIMEOUT: inactive_timeout,
                }
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )


async def test_zha_sensor_shows_inactive_when_last_seen_exceeds_timeout(
    hass: HomeAssistant,
) -> None:
    """Test ZHA sensor shows Inactive when the device has not been seen within the timeout."""
    entry = _zha_config_entry(inactive_timeout=5)
    entry.add_to_hass(hass)

    # last_seen is 10 minutes ago — exceeds the 5-minute timeout
    old_timestamp = (datetime.now() - timedelta(minutes=10)).timestamp()

    with patch(
        "homeassistant.components.connectivity_monitor.sensor.async_get_zha_device_last_seen",
        AsyncMock(return_value=old_timestamp),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.connectivity_monitor_zha_back_door_sensor")
    assert state is not None
    assert state.state == "Inactive"
    assert state.attributes["ieee"] == "00:11:22:33:44:55:66:77"
    assert state.attributes["monitor_type"] == "zha"
    assert state.attributes["timeout_minutes"] == 5
    assert state.attributes["last_seen"] is not None
    assert state.attributes["minutes_ago"] >= 10.0
    assert state.attributes["icon"] == "mdi:lan-disconnect"


async def test_zha_sensor_shows_inactive_when_device_not_found_in_zha(
    hass: HomeAssistant,
) -> None:
    """Test ZHA sensor shows Inactive when last_seen returns None (device absent from ZHA)."""
    entry = _zha_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.sensor.async_get_zha_device_last_seen",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.connectivity_monitor_zha_back_door_sensor")
    assert state is not None
    assert state.state == "Inactive"
    assert state.attributes["ieee"] == "00:11:22:33:44:55:66:77"
    assert state.attributes["monitor_type"] == "zha"
    # last_seen and minutes_ago are absent when the device has never reported
    assert "last_seen" not in state.attributes
    assert "minutes_ago" not in state.attributes
    assert state.attributes["icon"] == "mdi:lan-disconnect"


async def test_zha_sensor_shows_unknown_when_coordinator_has_no_data(
    hass: HomeAssistant,
) -> None:
    """Test ZHA sensor shows Unknown when the coordinator returns no data for the target."""
    entry = _zha_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.connectivity_monitor.sensor."
        "ConnectivityMonitorCoordinator._async_update_data",
        AsyncMock(return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.connectivity_monitor_zha_back_door_sensor")
    assert state is not None
    assert state.state == "Unknown"
    assert state.attributes["icon"] == "mdi:lan-disconnect"


# ---------------------------------------------------------------------------
# Parametrized alert logic tests for non-network protocols
# ---------------------------------------------------------------------------

_PROTO_ALERT_PARAMS = [
    pytest.param(
        PROTOCOL_ZHA,
        "connectivity_monitor_zha",
        {
            CONF_PROTOCOL: PROTOCOL_ZHA,
            CONF_HOST: "zha:AA:BB:CC:11:22:33:44:55",
            CONF_ZHA_IEEE: "AA:BB:CC:11:22:33:44:55",
            "device_name": "Door Sensor",
            CONF_INACTIVE_TIMEOUT: DEFAULT_INACTIVE_TIMEOUT,
            CONF_ALERT_GROUP: "family",
            CONF_ALERT_DELAY: 2,
            CONF_ALERT_ACTION: "automation.door_recovery",
            CONF_ALERT_ACTION_DELAY: 3,
        },
        "sensor.connectivity_monitor_zha_door_sensor",
        "homeassistant.components.connectivity_monitor.sensor.async_get_zha_device_last_seen",
        # active_patch_value: recent timestamp → Active
        None,  # replaced per-test using datetime.now()
        "AA:BB:CC:11:22:33:44:55",
        id="zha",
    ),
    pytest.param(
        PROTOCOL_MATTER,
        "connectivity_monitor_matter",
        {
            CONF_PROTOCOL: PROTOCOL_MATTER,
            CONF_HOST: "matter:1-9999",
            CONF_MATTER_NODE_ID: "1-9999",
            "device_name": "Smart Plug",
            CONF_ALERT_GROUP: "family",
            CONF_ALERT_DELAY: 2,
            CONF_ALERT_ACTION: "automation.plug_recovery",
            CONF_ALERT_ACTION_DELAY: 3,
        },
        "sensor.connectivity_monitor_matter_smart_plug",
        "homeassistant.components.connectivity_monitor.sensor.async_get_matter_device_active",
        True,
        "1-9999",
        id="matter",
    ),
    pytest.param(
        PROTOCOL_ESPHOME,
        "connectivity_monitor_esphome",
        {
            CONF_PROTOCOL: PROTOCOL_ESPHOME,
            CONF_HOST: "esphome:esp-node-1",
            CONF_ESPHOME_DEVICE_ID: "esp-node-1",
            "device_name": "ESP Node",
            CONF_ALERT_GROUP: "family",
            CONF_ALERT_DELAY: 2,
            CONF_ALERT_ACTION: "automation.esp_recovery",
            CONF_ALERT_ACTION_DELAY: 3,
        },
        "sensor.connectivity_monitor_esphome_esp_node",
        "homeassistant.components.connectivity_monitor.sensor.async_get_esphome_device_active",
        True,
        "esp-node-1",
        id="esphome",
    ),
    pytest.param(
        PROTOCOL_BLUETOOTH,
        "connectivity_monitor_bluetooth",
        {
            CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
            CONF_HOST: "bluetooth:11:22:33:44:55:66",
            CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66",
            "device_name": "BT Tag",
            CONF_ALERT_GROUP: "family",
            CONF_ALERT_DELAY: 2,
            CONF_ALERT_ACTION: "automation.bt_recovery",
            CONF_ALERT_ACTION_DELAY: 3,
        },
        "sensor.connectivity_monitor_bluetooth_bt_tag",
        "homeassistant.components.connectivity_monitor.sensor.async_get_bluetooth_device_details",
        {"active": True, "device_found": True},
        "11:22:33:44:55:66",
        id="bluetooth",
    ),
]


def _make_alerting_proto_entry(
    protocol: str,
    entry_unique_id: str,
    target: dict,
    *,
    alert_delay: int = 2,
    action_delay: int = 3,
) -> MockConfigEntry:
    """Return a protocol-specific config entry with alert settings."""
    patched_target = {
        **target,
        CONF_ALERT_DELAY: alert_delay,
        CONF_ALERT_ACTION_DELAY: action_delay,
    }
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{protocol} Monitor",
        unique_id=entry_unique_id,
        version=2,
        data={
            CONF_TARGETS: [patched_target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )


@pytest.mark.parametrize(
    (
        "protocol",
        "entry_unique_id",
        "target",
        "entity_id",
        "patch_path",
        "active_patch_value",
        "expected_identifier",
    ),
    _PROTO_ALERT_PARAMS,
)
async def test_protocol_alert_triggers_notification_and_action_after_delays(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    protocol: str,
    entry_unique_id: str,
    target: dict,
    entity_id: str,
    patch_path: str,
    active_patch_value: object,
    expected_identifier: str,
) -> None:
    """Test that notification and action fire after their respective delays for non-network sensors."""
    # ZHA uses a timestamp; supply a recent one so the sensor starts Active.
    if protocol == PROTOCOL_ZHA:
        active_patch_value = datetime.now().timestamp()

    entry = _make_alerting_proto_entry(
        protocol, entry_unique_id, target, alert_delay=2, action_delay=3
    )
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with patch(patch_path, AsyncMock(return_value=active_patch_value)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Drive sensor to Inactive
    hass.states.async_set(entity_id, "Inactive")
    await hass.async_block_till_done()

    # Tick 1 min — before alert_delay=2, nothing fires
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 0
    assert len(alert_events) == 0

    # Tick 1 more min — hits alert_delay=2, notification fires
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert (
        f"❌ Device {target['device_name']} ({expected_identifier})"
        in notify_calls[0].data["message"]
    )
    assert "inactive for 2 minutes" in notify_calls[0].data["message"]
    assert len(alert_events) == 0

    # Tick 1 more min — hits action_delay=3, action event fires
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1
    assert alert_events[0].data["device_name"] == target["device_name"]
    assert alert_events[0].data["device_address"] == expected_identifier
    assert alert_events[0].data["minutes_offline"] == 3


@pytest.mark.parametrize(
    (
        "protocol",
        "entry_unique_id",
        "target",
        "entity_id",
        "patch_path",
        "active_patch_value",
        "expected_identifier",
    ),
    _PROTO_ALERT_PARAMS,
)
async def test_protocol_alert_sends_recovery_after_confirmed_reactivation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    protocol: str,
    entry_unique_id: str,
    target: dict,
    entity_id: str,
    patch_path: str,
    active_patch_value: object,
    expected_identifier: str,
) -> None:
    """Test recovery notification and action fire after the device sustains Active state."""
    if protocol == PROTOCOL_ZHA:
        active_patch_value = datetime.now().timestamp()

    entry = _make_alerting_proto_entry(
        protocol, entry_unique_id, target, alert_delay=1, action_delay=1
    )
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with patch(patch_path, AsyncMock(return_value=active_patch_value)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(entity_id, "Inactive")
    await hass.async_block_till_done()

    # Trigger outage notification + action
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1

    # Device recovers
    hass.states.async_set(entity_id, "Active")
    await hass.async_block_till_done()

    # One more minute sustained → recovery fires
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify_calls) == 2
    assert (
        f"✅ Device {target['device_name']} ({expected_identifier})"
        in notify_calls[1].data["message"]
    )
    assert "active again" in notify_calls[1].data["message"]
    assert len(alert_events) == 2
    assert alert_events[1].data["recovered"] is True


@pytest.mark.parametrize(
    (
        "protocol",
        "entry_unique_id",
        "target",
        "entity_id",
        "patch_path",
        "active_patch_value",
        "expected_identifier",
    ),
    _PROTO_ALERT_PARAMS,
)
async def test_protocol_alert_does_not_repeat_notification_or_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    protocol: str,
    entry_unique_id: str,
    target: dict,
    entity_id: str,
    patch_path: str,
    active_patch_value: object,
    expected_identifier: str,
) -> None:
    """Test that repeated timer ticks do not emit duplicate outage notifications or actions."""
    if protocol == PROTOCOL_ZHA:
        active_patch_value = datetime.now().timestamp()

    entry = _make_alerting_proto_entry(
        protocol, entry_unique_id, target, alert_delay=1, action_delay=1
    )
    entry.add_to_hass(hass)

    notify_calls = async_mock_service(hass, "notify", "family")
    alert_events = async_capture_events(hass, "connectivity_monitor_alert")

    with patch(patch_path, AsyncMock(return_value=active_patch_value)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(entity_id, "Inactive")
    await hass.async_block_till_done()

    # First tick — notification + action fire
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(notify_calls) == 1
    assert len(alert_events) == 1

    # Additional ticks — nothing more should fire
    for _ in range(3):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(notify_calls) == 1
    assert len(alert_events) == 1


# ---------------------------------------------------------------------------
# ADOverviewSensor tests
# ---------------------------------------------------------------------------


def _ad_dc_config_entry() -> MockConfigEntry:
    """Return a network config entry with all AD DC ports for a domain controller."""
    ad_ports = list(AD_DC_PORTS.keys())  # [88, 139, 389, 445, 464, 636, 3268, 3269]
    return MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.30",
                    CONF_PROTOCOL: PROTOCOL_TCP,
                    CONF_PORT: port,
                    "device_name": "Domain Controller",
                }
                for port in ad_ports
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )


async def test_ad_overview_sensor_shows_connected_when_all_ports_up(
    hass: HomeAssistant,
) -> None:
    """Test AD overview sensor reports Connected when all AD DC ports respond."""
    entry = _ad_dc_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": True,
                    "latency": 1.5,
                    "resolved_ip": "192.168.1.30",
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.connectivity_monitor_domain_controller_ad")
    assert state is not None
    assert state.state == "Connected"
    assert state.attributes["icon"] == "mdi:domain"
    assert state.attributes["host"] == "192.168.1.30"
    assert state.attributes["device_name"] == "Domain Controller"
    ad_services = state.attributes["ad_services"]
    assert len(ad_services) == len(AD_DC_PORTS)
    assert all(svc["status"] == "Connected" for svc in ad_services)
    assert all(svc["latency_ms"] == 1.5 for svc in ad_services)
    assert {svc["port"] for svc in ad_services} == set(AD_DC_PORTS.keys())


async def test_ad_overview_sensor_shows_partially_connected_when_some_ports_down(
    hass: HomeAssistant,
) -> None:
    """Test AD overview sensor reports Partially Connected when only some ports respond."""
    entry = _ad_dc_config_entry()
    entry.add_to_hass(hass)

    ad_ports = list(AD_DC_PORTS.keys())
    # First half connected, second half not
    connected_ports = set(ad_ports[: len(ad_ports) // 2])

    def _update_side_effect(target: dict) -> dict:
        port = target.get(CONF_PORT)
        connected = port in connected_ports
        return {
            "connected": connected,
            "latency": 2.0 if connected else None,
            "resolved_ip": "192.168.1.30",
            "mac_address": None,
        }

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(side_effect=_update_side_effect),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.connectivity_monitor_domain_controller_ad")
    assert state is not None
    assert state.state == "Partially Connected"
    assert state.attributes["icon"] == "mdi:domain-remove"
    ad_services = state.attributes["ad_services"]
    assert len(ad_services) == len(AD_DC_PORTS)
    connected_count = sum(1 for svc in ad_services if svc["status"] == "Connected")
    not_connected_count = sum(
        1 for svc in ad_services if svc["status"] == "Not Connected"
    )
    assert connected_count == len(connected_ports)
    assert not_connected_count == len(ad_ports) - len(connected_ports)


async def test_ad_overview_sensor_shows_not_connected_when_all_ports_down(
    hass: HomeAssistant,
) -> None:
    """Test AD overview sensor reports Not Connected when no AD DC port responds."""
    entry = _ad_dc_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(
                return_value={
                    "connected": False,
                    "latency": None,
                    "resolved_ip": None,
                    "mac_address": None,
                }
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.connectivity_monitor_domain_controller_ad")
    assert state is not None
    assert state.state == "Not Connected"
    assert state.attributes["icon"] == "mdi:domain-off"
    ad_services = state.attributes["ad_services"]
    assert len(ad_services) == len(AD_DC_PORTS)
    assert all(svc["status"] == "Not Connected" for svc in ad_services)
    assert all("latency_ms" not in svc for svc in ad_services)


async def test_overview_sensor_shows_partially_connected(
    hass: HomeAssistant,
) -> None:
    """Test OverviewSensor reports Partially Connected when only some targets are up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Router",
                },
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_TCP,
                    CONF_PORT: 443,
                    "device_name": "Router",
                },
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    call_count = 0

    async def _varying_update(target: dict) -> dict:
        """Return connected for the first call (ICMP), disconnected for the second (TCP)."""
        nonlocal call_count
        call_count += 1
        connected = call_count == 1
        return {
            "connected": connected,
            "latency": 3.0 if connected else None,
            "resolved_ip": "192.168.1.1",
            "mac_address": None,
        }

    with (
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_prepare_host",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.connectivity_monitor.coordinator."
            "NetworkProbe.async_update_target",
            AsyncMock(side_effect=_varying_update),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.connectivity_monitor_router_overall")
    assert state is not None
    assert state.state == "Partially Connected"
    assert state.attributes["icon"] == "mdi:network-strength-2"
    services = state.attributes["monitored_services"]
    assert len(services) == 2
    connected_svcs = [s for s in services if s["status"] == "Connected"]
    disconnected_svcs = [s for s in services if s["status"] == "Disconnected"]
    assert len(connected_svcs) == 1
    assert len(disconnected_svcs) == 1
    assert connected_svcs[0]["protocol"] == PROTOCOL_ICMP
    assert disconnected_svcs[0]["protocol"] == PROTOCOL_TCP
