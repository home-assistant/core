"""Test for the switchbot_cloud binary sensors."""

from unittest.mock import patch

import pytest
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    CONTACT_SENSOR_INFO,
    HUB3_INFO,
    MOTION_SENSOR_INFO,
    WATER_DETECTOR_INFO,
    configure_integration,
)

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
    ("device_info", "index"),
    [
        (CONTACT_SENSOR_INFO, 0),
        (CONTACT_SENSOR_INFO, 2),
        (HUB3_INFO, 3),
        (MOTION_SENSOR_INFO, 4),
        (WATER_DETECTOR_INFO, 5),
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    device_info: Device,
    index: int,
) -> None:
    """Test binary sensors."""

    mock_list_devices.return_value = [device_info]

    json_data = await async_load_json_array_fixture(hass, "status.json", DOMAIN)
    mock_get_status.return_value = json_data[index]

    with patch(
        "homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
