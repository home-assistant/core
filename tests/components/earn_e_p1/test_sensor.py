"""Tests for the EARN-E P1 Meter sensor platform."""

from __future__ import annotations

from homeassistant.components.earn_e_p1.coordinator import EarnEP1Coordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import DOMAIN, MOCK_SERIAL

from tests.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> EarnEP1Coordinator:
    """Set up the integration and return the coordinator."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry.runtime_data


async def test_sensors_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that sensors are created on setup."""
    coordinator = await _setup_integration(hass, mock_config_entry)

    coordinator.async_set_updated_data({"power_delivered": 1.234})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is not None
    assert state.state == "1.234"


async def test_sensor_unavailable_without_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor is unavailable when no data has been received."""
    await _setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is not None
    assert state.state == "unavailable"


async def test_sensor_value_none_when_key_missing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor returns unknown when its key is missing from data."""
    coordinator = await _setup_integration(hass, mock_config_entry)

    coordinator.async_set_updated_data({"power_delivered": 1.0})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.earn_e_p1_meter_power_exported")
    assert state is not None
    assert state.state == "unknown"


async def test_sensor_native_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor returns correct native value."""
    coordinator = await _setup_integration(hass, mock_config_entry)

    coordinator.async_set_updated_data(
        {
            "power_delivered": 2.5,
            "voltage_l1": 230.1,
            "energy_delivered_tariff1": 12345.678,
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.earn_e_p1_meter_power_imported").state == "2.5"
    assert hass.states.get("sensor.earn_e_p1_meter_voltage_l1").state == "230.1"
    assert (
        hass.states.get("sensor.earn_e_p1_meter_energy_imported_tariff_1").state
        == "12345.678"
    )


async def test_device_info(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test device info is correct."""
    coordinator = await _setup_integration(hass, mock_config_entry)

    coordinator.async_set_updated_data({"power_delivered": 1.0})
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})
    assert device is not None
    assert device.name == "EARN-E P1 Meter"
    assert device.manufacturer == "EARN-E"


async def test_sensor_unique_id_uses_serial(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that sensor unique_id uses serial with the data key."""
    coordinator = await _setup_integration(hass, mock_config_entry)

    coordinator.async_set_updated_data({"power_delivered": 1.0})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.earn_e_p1_meter_power_imported")
    assert entry is not None
    assert entry.unique_id == f"{MOCK_SERIAL}_power_delivered"


async def test_wifi_rssi_disabled_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that Wi-Fi RSSI sensor is disabled by default."""
    await _setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.earn_e_p1_meter_wi_fi_rssi")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
