"""Test for the switchbot_cloud binary sensors."""

from unittest.mock import patch

import pytest
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES,
)
from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration

from tests.common import async_load_json_array_fixture, snapshot_platform


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

    with patch(
        "homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        entry = await configure_integration(hass)

    # Assert no binary sensor entities were created for unsupported device type
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len([e for e in entities if e.domain == "binary_sensor"]) == 0


@pytest.mark.parametrize(
    "device_model",
    list(BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES),
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

    with patch(
        "homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "device_model",
    list(BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES),
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
    with patch(
        "homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_id_list = [entity.unique_id for entity in entities]

    assert len(entities) == len(
        BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device_model]
    )
    for target in BINARY_SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES[device_model]:
        assert f"test-device-id-1_{target.key}" in unique_id_list
