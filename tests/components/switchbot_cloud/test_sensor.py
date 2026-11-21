"""Test for the switchbot_cloud sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import async_load_json_array_fixture, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud import DOMAIN
from homeassistant.components.switchbot_cloud.sensor import (
    SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_WEBHOOK_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import entity_registry as er

from . import configure_integration

LOCK_ULTRA_MAX_MAC = "AABBCCDDEEFF"
DOOR_ENTITY_ID = "binary_sensor.lock_ultra_max_door"
LOCK_STATE_ENTITY_ID = "sensor.lock_ultra_max_lock_state"

SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES_WITHOUT_RELAY_SWITCH_2PM = (
    SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES.copy()
)
SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES_WITHOUT_RELAY_SWITCH_2PM.pop("Relay Switch 2PM")


@pytest.mark.parametrize(
    "device_model",
    list(SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES),
)
async def test_no_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
    device_model,
) -> None:
    """Test existed sensors entity are unknown without coordinator data."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="test-device-id-1",
            deviceName="test-device-name-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = None

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "device_model",
    list(SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES_WITHOUT_RELAY_SWITCH_2PM),
)
async def test_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
    device_model,
) -> None:
    """Test existed sensors entity with coordinator data."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="test-device-id-1",
            deviceName="test-device-name-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    json_data = await async_load_json_array_fixture(hass, "sensor_status.json", DOMAIN)

    mock_get_status.side_effect = [
        item for item in json_data if item.get("deviceType") == device_model
    ]
    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_id_list = [entity.unique_id for entity in entities]

    assert len(entities) == len(SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device_model])
    for target in SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device_model]:
        assert f"test-device-id-1_{target.key}" in unique_id_list


async def test_relay_switch_2pm_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    mock_setup_webhook,
) -> None:
    """Test existed sensors entity with coordinator data."""
    device_model = "Relay Switch 2PM"
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="test-device-id-1",
            deviceName="test-device-name-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    json_data = await async_load_json_array_fixture(hass, "sensor_status.json", DOMAIN)

    mock_get_status.side_effect = [
        item for item in json_data if item.get("deviceType") == device_model
    ]
    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_id_list = [entity.unique_id for entity in entities]

    assert len(entities) == 8
    for target in SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device_model]:
        assert f"test-device-id-1-{target.key}-1" in unique_id_list
        assert f"test-device-id-1-{target.key}-2" in unique_id_list


async def test_unsupported_device_type(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test that unsupported device types do not create sensors."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="unsupported-id-1",
            deviceName="unsupported-device",
            deviceType="UnsupportedDevice",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {}

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    # Assert no sensor entities were created for unsupported device type
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len([e for e in entities if e.domain == "sensor"]) == 0


@pytest.mark.usefixtures("mock_delete_webhook", "mock_setup_webhook")
@pytest.mark.parametrize(
    (
        "polled_door",
        "expected_polled_door",
        "polled_lock",
        "expected_polled_lock",
        "webhook_door",
        "webhook_lock",
        "expected_door",
        "expected_lock",
    ),
    [
        pytest.param(
            "opened",
            STATE_ON,
            "locked",
            "locked",
            "CLOSED",
            "UNLOCKED",
            STATE_OFF,
            "unlocked",
            id="closed_unlocked",
        ),
        pytest.param(
            "closed",
            STATE_OFF,
            "unlocked",
            "unlocked",
            "OPENED",
            "LOCKED",
            STATE_ON,
            "locked",
            id="opened_locked",
        ),
        pytest.param(
            "opened",
            STATE_ON,
            "latchBoltLocked",
            "latch_bolt_locked",
            "CLOSED",
            "LATCHBOLTLOCKED",
            STATE_OFF,
            "latch_bolt_locked",
            id="latch_bolt_locked",
        ),
        pytest.param(
            "closed",
            STATE_OFF,
            "halfLocked",
            "half_locked",
            "OPENED",
            "HALFLOCKED",
            STATE_ON,
            "half_locked",
            id="half_locked",
        ),
        pytest.param(
            "opened",
            STATE_ON,
            "jammed",
            "jammed",
            "CLOSED",
            "JAMMED",
            STATE_OFF,
            "jammed",
            id="jammed",
        ),
        pytest.param(
            "closed",
            STATE_OFF,
            "locking",
            "locking",
            "OPENED",
            "LOCKING",
            STATE_ON,
            "locking",
            id="locking",
        ),
        pytest.param(
            "opened",
            STATE_ON,
            "unlocking",
            "unlocking",
            "CLOSED",
            "UNLOCKING",
            STATE_OFF,
            "unlocking",
            id="unlocking",
        ),
        pytest.param(
            "opened",
            STATE_ON,
            "locked",
            "locked",
            "OPENED",
            "SOMETHINGNEW",
            STATE_ON,
            STATE_UNKNOWN,
            id="unknown_lock_state",
        ),
    ],
)
async def test_uppercase_webhook_updates_door_and_lock_state(
    hass: HomeAssistant,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    mock_get_webook_configuration: AsyncMock,
    hass_client_no_auth: ClientSessionGenerator,
    polled_door: str,
    expected_polled_door: str,
    polled_lock: str,
    expected_polled_lock: str,
    webhook_door: str,
    webhook_lock: str,
    expected_door: str,
    expected_lock: str,
) -> None:
    """Uppercase webhook doorState and lockState still update the sensors.

    Polled status uses camel case (``latchBoltLocked``). Lock Ultra Max webhooks
    send the same words uppercased (``LATCHBOLTLOCKED``).
    """
    await async_process_ha_core_config(hass, {"external_url": "https://example.com"})
    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId=LOCK_ULTRA_MAX_MAC,
            deviceName="Lock Ultra Max",
            deviceType="Smart Lock Ultra Max",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {
        "deviceId": LOCK_ULTRA_MAX_MAC,
        "lockState": polled_lock,
        "doorState": polled_door,
        "battery": 98,
        "calibrate": True,
    }

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(DOOR_ENTITY_ID).state == expected_polled_door
    assert hass.states.get(LOCK_STATE_ENTITY_ID).state == expected_polled_lock

    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{entry.data[CONF_WEBHOOK_ID]}",
        json={
            "eventType": "changeReport",
            "eventVersion": "1",
            "context": {
                "deviceMac": LOCK_ULTRA_MAX_MAC,
                "deviceType": "Lock Ultra Max",
                "doorState": webhook_door,
                "lockState": webhook_lock,
                "battery": 98,
                "timeOfSample": 1794498027563,
            },
        },
    )
    assert response.status == 200
    await hass.async_block_till_done()

    assert hass.states.get(DOOR_ENTITY_ID).state == expected_door
    assert hass.states.get(LOCK_STATE_ENTITY_ID).state == expected_lock
