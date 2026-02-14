"""Test the Proxmox VE sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.sensor import ProxmoxStorageSensor
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_storage_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all storage disk sensors."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_storage_sensor_native_value_and_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ProxmoxStorageSensor native_value and extra_state_attributes."""
    storage_data = [
        {
            "storage": "local",
            "type": "dir",
            "total": 500000000000,
            "used": 100000000000,
            "avail": 400000000000,
        },
    ]
    coordinator = DataUpdateCoordinator(
        hass,
        MagicMock(),
        name="test",
        update_method=lambda: None,
        config_entry=mock_config_entry,
    )
    coordinator.data = storage_data
    coordinator.last_update_success = True

    sensor = ProxmoxStorageSensor(
        coordinator=coordinator,
        host_name="127.0.0.1",
        node_name="pve1",
        storage_id="local",
        storage_type="dir",
    )

    # State = % free (avail/total*100); 400e9/500e9 = 80%
    assert sensor.native_value == 80.0
    attrs = sensor.extra_state_attributes
    assert attrs["total_gib"] == 465.66
    assert attrs["free_gib"] == 372.53
    assert attrs["percent_used"] == 20.0
    assert attrs["used_gib"] == 93.13
    assert sensor.available is True


async def test_storage_sensor_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ProxmoxStorageSensor is unavailable when coordinator has no data."""
    coordinator = DataUpdateCoordinator(
        hass,
        MagicMock(),
        name="test",
        update_method=lambda: None,
        config_entry=mock_config_entry,
    )
    coordinator.data = None
    coordinator.last_update_success = True

    sensor = ProxmoxStorageSensor(
        coordinator=coordinator,
        host_name="127.0.0.1",
        node_name="pve1",
        storage_id="local",
        storage_type="dir",
    )

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {
        "total_gib": None,
        "free_gib": None,
        "percent_used": None,
        "used_gib": None,
    }
    assert sensor.available is False


async def test_storage_sensor_missing_storage_in_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ProxmoxStorageSensor when storage id is not in coordinator data."""
    coordinator = DataUpdateCoordinator(
        hass,
        MagicMock(),
        name="test",
        update_method=lambda: None,
        config_entry=mock_config_entry,
    )
    coordinator.data = [
        {"storage": "other", "type": "dir", "total": 100, "used": 50, "avail": 50},
    ]
    coordinator.last_update_success = True

    sensor = ProxmoxStorageSensor(
        coordinator=coordinator,
        host_name="127.0.0.1",
        node_name="pve1",
        storage_id="local",
        storage_type="dir",
    )

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {
        "total_gib": None,
        "free_gib": None,
        "percent_used": None,
        "used_gib": None,
    }
    assert sensor.available is False
