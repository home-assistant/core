"""Test updating sensors in the victron_ble integration."""

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fixtures import (
    VICTRON_BATTERY_MONITOR_SERVICE_INFO,
    VICTRON_BATTERY_MONITOR_TOKEN,
    VICTRON_DC_ENERGY_METER_SERVICE_INFO,
    VICTRON_DC_ENERGY_METER_TOKEN,
    VICTRON_SOLAR_CHARGER_SERVICE_INFO,
    VICTRON_SOLAR_CHARGER_TOKEN,
    VICTRON_VEBUS_SERVICE_INFO,
    VICTRON_VEBUS_TOKEN,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    (
        "service_info",
        "access_token",
    ),
    [
        (VICTRON_BATTERY_MONITOR_SERVICE_INFO, VICTRON_BATTERY_MONITOR_TOKEN),
        (VICTRON_DC_ENERGY_METER_SERVICE_INFO, VICTRON_DC_ENERGY_METER_TOKEN),
        (VICTRON_SOLAR_CHARGER_SERVICE_INFO, VICTRON_SOLAR_CHARGER_TOKEN),
        (VICTRON_VEBUS_SERVICE_INFO, VICTRON_VEBUS_TOKEN),
    ],
    ids=["battery_monitor", "dc_energy_meter", "solar_charger", "vebus"],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry_added_to_hass: MockConfigEntry,
    service_info: BluetoothServiceInfo,
    access_token: str,
) -> None:
    """Test sensor entities."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Initially no entities should be created until bluetooth data is received
    assert len(hass.states.async_all()) == 0

    # Inject bluetooth service info to trigger entity creation
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    # Use snapshot testing to verify all entity states and registry entries
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
