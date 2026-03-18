"""Test updating sensors in the victron_ble integration."""

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.victron_ble.const import DOMAIN, VICTRON_IDENTIFIER
from homeassistant.const import CONF_ACCESS_TOKEN
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

# Crafted solar charger advertisements with specific charger_error values.
# These are real encrypted payloads using VICTRON_SOLAR_CHARGER_TOKEN.
SOLAR_CHARGER_ERROR_PAYLOADS = {
    # ChargerError.NO_ERROR -> state "no_error"
    "no_error": "100242a0016207adceb37b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.INTERNAL_SUPPLY_A -> mapped to state "internal_supply"
    "internal_supply": "100242a0016207adce787b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.VOLTAGE_HIGH -> state "voltage_high"
    "voltage_high": "100242a0016207adceb17b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
    # ChargerError.NETWORK_A -> mapped to state "network"
    "network": "100242a0016207adcef77b605d7e0ee21b24df5c0404040410951e81ea42b0492e356ad5ed8f7eb7",
}


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


@pytest.mark.usefixtures("enable_bluetooth")
@pytest.mark.parametrize(
    ("payload_hex", "expected_state"),
    [
        (SOLAR_CHARGER_ERROR_PAYLOADS["no_error"], "no_error"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["internal_supply"], "internal_supply"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["voltage_high"], "voltage_high"),
        (SOLAR_CHARGER_ERROR_PAYLOADS["network"], "network"),
    ],
    ids=["no_error", "internal_supply_variant", "voltage_high", "network_variant"],
)
async def test_charger_error_state(
    hass: HomeAssistant,
    payload_hex: str,
    expected_state: str,
) -> None:
    """Test that charger error values are correctly mapped to sensor states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: VICTRON_SOLAR_CHARGER_TOKEN},
        unique_id=VICTRON_SOLAR_CHARGER_SERVICE_INFO.address,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_info = BluetoothServiceInfo(
        name="Solar Charger",
        address=VICTRON_SOLAR_CHARGER_SERVICE_INFO.address,
        rssi=-60,
        manufacturer_data={VICTRON_IDENTIFIER: bytes.fromhex(payload_hex)},
        service_data={},
        service_uuids=[],
        source="local",
    )

    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solar_charger_charger_error")
    assert state is not None
    assert state.state == expected_state
