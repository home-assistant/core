"""Test for the switchbot_cloud sensors."""

from unittest.mock import patch

import pytest
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    CONTACT_SENSOR_INFO,
    HUB3_INFO,
    METER_INFO,
    MOTION_SENSOR_INFO,
    WATER_DETECTOR_INFO,
    configure_integration,
)

from tests.common import async_load_json_array_fixture, snapshot_platform


@pytest.mark.parametrize(
    ("device_info", "index"),
    [
        (METER_INFO, 0),
        (METER_INFO, 1),
        (CONTACT_SENSOR_INFO, 2),
        (HUB3_INFO, 3),
        (MOTION_SENSOR_INFO, 4),
        (WATER_DETECTOR_INFO, 5),
    ],
)
async def test_meter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    device_info: Device,
    index: int,
) -> None:
    """Test all sensors."""

async def test_plug_mini_eu(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test plug_mini_eu Used Electricity."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="Plug-id-1",
            deviceName="Plug-1",
            deviceType="Plug Mini (EU)",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        {
            "usedElectricity": 3255,
            "deviceId": "94A99054855E",
            "deviceType": "Plug Mini (EU)",
        },
    ]

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "device_model",
    [
        "Meter",
        "Plug Mini (EU)",
    ],
)
async def test_no_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    device_model,
) -> None:
    """Test meter sensors are unknown without coordinator data."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="meter-id-1",
            deviceName="meter-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    json_data = await async_load_json_array_fixture(hass, "status.json", DOMAIN)
    mock_get_status.return_value = json_data[index]

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


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
