"""Test for the switchbot_cloud sensors."""

from unittest.mock import patch

from switchbot_api import Device
from syrupy import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration

from tests.common import load_json_object_fixture, snapshot_platform


async def test_meter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test Meter sensors."""

    mock_list_devices.return_value = [
        Device(
            deviceId="meter-id-1",
            deviceName="meter-1",
            deviceType="Meter",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = load_json_object_fixture("meter_status.json", DOMAIN)

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_meter_no_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test meter sensors are unknown without coordinator data."""
    mock_list_devices.return_value = [
        Device(
            deviceId="meter-id-1",
            deviceName="meter-1",
            deviceType="Meter",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = None

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
