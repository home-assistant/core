"""Test for the switchbot_cloud sensors."""

from unittest.mock import patch

from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration

from tests.common import async_load_json_object_fixture, snapshot_platform


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
            version="V1.0",
            deviceId="meter-id-1",
            deviceName="meter-1",
            deviceType="Meter",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = await async_load_json_object_fixture(
        hass, "meter_status.json", DOMAIN
    )

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.SENSOR]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_relay_switch_2pm(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test Relay Switch 2PM sensors."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="switch-id-1",
            deviceName="switch-1",
            deviceType="Relay Switch 2PM",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {
        "switch1Status": 1,
        "switch1Voltage": 235.5,
        "switch1Power": 0,
        "switch1ElectricCurrent": 3,
        "switch1UsedElectricity": 0,
        "deviceId": "C04E30DF93A6",
        "deviceType": "Relay Switch 2PM",
        "hubDeviceId": "C04E30DF93A6",
    }

    await configure_integration(hass)


async def test_relay_switch_2pm_no_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test meter sensors are unknown without coordinator data."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="switch-id-1",
            deviceName="switch-1",
            deviceType="Relay Switch 2PM",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = None

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
            version="V1.0",
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
