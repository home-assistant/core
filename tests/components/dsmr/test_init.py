"""Tests for the DSMR integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.dsmr.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("dsmr_version", "old_unique_id", "new_unique_id"),
    [
        ("5", "1234_Power_Consumption", "1234_current_electricity_usage"),
        ("5", "1234_Power_Production", "1234_current_electricity_delivery"),
        ("5", "1234_Power_Tariff", "1234_electricity_active_tariff"),
        ("5", "1234_Energy_Consumption_(tarif_1)", "1234_electricity_used_tariff_1"),
        ("5", "1234_Energy_Consumption_(tarif_2)", "1234_electricity_used_tariff_2"),
        (
            "5",
            "1234_Energy_Production_(tarif_1)",
            "1234_electricity_delivered_tariff_1",
        ),
        (
            "5",
            "1234_Energy_Production_(tarif_2)",
            "1234_electricity_delivered_tariff_2",
        ),
        (
            "5",
            "1234_Power_Consumption_Phase_L1",
            "1234_instantaneous_active_power_l1_positive",
        ),
        (
            "5",
            "1234_Power_Consumption_Phase_L2",
            "1234_instantaneous_active_power_l2_positive",
        ),
        (
            "5",
            "1234_Power_Consumption_Phase_L3",
            "1234_instantaneous_active_power_l3_positive",
        ),
        (
            "5",
            "1234_Power_Production_Phase_L1",
            "1234_instantaneous_active_power_l1_negative",
        ),
        (
            "5",
            "1234_Power_Production_Phase_L2",
            "1234_instantaneous_active_power_l2_negative",
        ),
        (
            "5",
            "1234_Power_Production_Phase_L3",
            "1234_instantaneous_active_power_l3_negative",
        ),
        ("5", "1234_Short_Power_Failure_Count", "1234_short_power_failure_count"),
        ("5", "1234_Long_Power_Failure_Count", "1234_long_power_failure_count"),
        ("5", "1234_Voltage_Sags_Phase_L1", "1234_voltage_sag_l1_count"),
        ("5", "1234_Voltage_Sags_Phase_L2", "1234_voltage_sag_l2_count"),
        ("5", "1234_Voltage_Sags_Phase_L3", "1234_voltage_sag_l3_count"),
        ("5", "1234_Voltage_Swells_Phase_L1", "1234_voltage_swell_l1_count"),
        ("5", "1234_Voltage_Swells_Phase_L2", "1234_voltage_swell_l2_count"),
        ("5", "1234_Voltage_Swells_Phase_L3", "1234_voltage_swell_l3_count"),
        ("5", "1234_Voltage_Phase_L1", "1234_instantaneous_voltage_l1"),
        ("5", "1234_Voltage_Phase_L2", "1234_instantaneous_voltage_l2"),
        ("5", "1234_Voltage_Phase_L3", "1234_instantaneous_voltage_l3"),
        ("5", "1234_Current_Phase_L1", "1234_instantaneous_current_l1"),
        ("5", "1234_Current_Phase_L2", "1234_instantaneous_current_l2"),
        ("5", "1234_Current_Phase_L3", "1234_instantaneous_current_l3"),
        ("5B", "1234_Max_power_per_phase", "1234_belgium_max_power_per_phase"),
        ("5B", "1234_Max_current_per_phase", "1234_belgium_max_current_per_phase"),
        ("5L", "1234_Energy_Consumption_(total)", "1234_electricity_imported_total"),
        ("5L", "1234_Energy_Production_(total)", "1234_electricity_exported_total"),
        ("5", "1234_Gas_Consumption", "1234_hourly_gas_meter_reading"),
        ("5B", "1234_Gas_Consumption", "1234_belgium_5min_gas_meter_reading"),
        ("2.2", "1234_Gas_Consumption", "1234_gas_meter_reading"),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
    dsmr_version: str,
    old_unique_id: str,
    new_unique_id: str,
) -> None:
    """Test migration of unique_id."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": dsmr_version,
            "serial_id": "1234",
            "serial_id_gas": "5678",
        },
        options={
            "time_between_update": 0,
        },
    )

    mock_entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="my_sensor",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=mock_entry,
    )
    assert entity.unique_id == old_unique_id

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, new_unique_id)
        == "sensor.my_sensor"
    )
