"""Test updating sensors in the victron_ble integration."""

import time

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fixtures import (
    VICTRON_AC_CHARGER_SERVICE_INFO,
    VICTRON_AC_CHARGER_TOKEN,
    VICTRON_BATTERY_MONITOR_SERVICE_INFO,
    VICTRON_BATTERY_MONITOR_TOKEN,
    VICTRON_DC_ENERGY_METER_SERVICE_INFO,
    VICTRON_DC_ENERGY_METER_TOKEN,
    VICTRON_SMART_LITHIUM_SERVICE_INFO,
    VICTRON_SMART_LITHIUM_TOKEN,
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
        (VICTRON_AC_CHARGER_SERVICE_INFO, VICTRON_AC_CHARGER_TOKEN),
        (VICTRON_BATTERY_MONITOR_SERVICE_INFO, VICTRON_BATTERY_MONITOR_TOKEN),
        (VICTRON_DC_ENERGY_METER_SERVICE_INFO, VICTRON_DC_ENERGY_METER_TOKEN),
        (VICTRON_SMART_LITHIUM_SERVICE_INFO, VICTRON_SMART_LITHIUM_TOKEN),
        (VICTRON_SOLAR_CHARGER_SERVICE_INFO, VICTRON_SOLAR_CHARGER_TOKEN),
        (VICTRON_VEBUS_SERVICE_INFO, VICTRON_VEBUS_TOKEN),
    ],
    ids=[
        "ac_charger",
        "battery_monitor",
        "dc_energy_meter",
        "smart_lithium",
        "solar_charger",
        "vebus",
    ],
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


from homeassistant.components.victron_ble import REAUTH_AFTER_FAILURES

from .fixtures import (
    VICTRON_VEBUS_BAD_KEY_SERVICE_INFO,
)

from tests.components.bluetooth import (
    inject_advertisement_with_time_and_source_connectable,
    generate_advertisement_data,
    generate_ble_device,
)


def _inject_bad_advertisement(hass: HomeAssistant, seq: int = 0) -> None:
    """Inject a VEBus advertisement that will fail decryption.

    Each call uses a unique payload suffix to avoid deduplication by the
    bluetooth manager, while keeping the VEBus device type header intact.
    """
    info = VICTRON_VEBUS_BAD_KEY_SERVICE_INFO
    # Vary the last byte so each injection is unique
    raw = bytearray(info.manufacturer_data[0x02E1])
    raw[-1] = seq & 0xFF
    device = generate_ble_device(address=info.address, name=info.name, details={})
    adv = generate_advertisement_data(
        local_name=info.name,
        manufacturer_data={0x02E1: bytes(raw)},
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        rssi=-60,
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, device, adv, time.monotonic(), "local", True
    )


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_triggered_after_consecutive_failures(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is triggered after consecutive decryption failures."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject bad advertisements (device type recognized but decryption fails)
    # Vary RSSI so the bluetooth manager doesn't deduplicate
    for i in range(REAUTH_AFTER_FAILURES):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Reauth flow should have been triggered
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_not_triggered_on_successful_decrypt(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is not triggered when decryption succeeds."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject bad advertisements, but fewer than the threshold
    for i in range(REAUTH_AFTER_FAILURES - 1):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Then inject a good advertisement to reset the counter
    inject_bluetooth_service_info(hass, VICTRON_VEBUS_SERVICE_INFO)
    await hass.async_block_till_done()

    # No reauth should have been triggered
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 0


@pytest.mark.usefixtures("enable_bluetooth")
async def test_reauth_triggered_only_once(
    hass: HomeAssistant,
    mock_config_entry_added_to_hass: MockConfigEntry,
) -> None:
    """Test that reauth is only triggered once per failure streak."""
    entry = mock_config_entry_added_to_hass

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Inject many bad advertisements
    for i in range(REAUTH_AFTER_FAILURES + 5):
        _inject_bad_advertisement(hass, seq=i)
        await hass.async_block_till_done()

    # Still only one reauth flow
    flows = hass.config_entries.flow.async_progress_by_handler("victron_ble")
    assert len(flows) == 1
