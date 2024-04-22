"""Test sensor entity for HomeWizard."""

from unittest.mock import MagicMock

from homewizard_energy.errors import RequestError
from homewizard_energy.models import Data
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homewizard import DOMAIN
from homeassistant.components.homewizard.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-P1",
            [
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_export",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_1",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_power",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_water_usage",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
                "sensor.gas_meter_gas",
                "sensor.heat_meter_energy",
                "sensor.inlet_heat_meter_none",
                "sensor.warm_water_meter_water",
                "sensor.water_meter_water",
            ],
        ),
        (
            "HWE-P1-zero-values",
            [
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_export",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_1",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_power",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_water_usage",
            ],
        ),
        (
            "HWE-SKT-11",
            [
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_power_phase_1",
                "sensor.device_power",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-SKT-21",
            [
                "sensor.device_apparent_power",
                "sensor.device_current",
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_power_factor",
                "sensor.device_power_phase_1",
                "sensor.device_power",
                "sensor.device_reactive_power",
                "sensor.device_voltage",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-WTR",
            [
                "sensor.device_total_water_usage",
                "sensor.device_water_usage",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "SDM230",
            [
                "sensor.device_apparent_power",
                "sensor.device_current",
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_power_factor",
                "sensor.device_power",
                "sensor.device_reactive_power",
                "sensor.device_voltage",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "SDM630",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_phase_1",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_power",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-KWH1",
            [
                "sensor.device_apparent_power",
                "sensor.device_current",
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_power_factor",
                "sensor.device_power",
                "sensor.device_reactive_power",
                "sensor.device_voltage",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-KWH3",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_energy_export",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_phase_1",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_power",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_wi_fi_ssid",
                "sensor.device_wi_fi_strength",
            ],
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_ids: list[str],
) -> None:
    """Test that sensor entity snapshots match."""
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id))
        assert snapshot(name=f"{entity_id}:state") == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert snapshot(name=f"{entity_id}:device-registry") == device_entry


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-P1",
            [
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_frequency",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-P1-unused-exports",
            [
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_export",
            ],
        ),
        (
            "HWE-SKT-11",
            [
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-SKT-21",
            [
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-WTR",
            [
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "SDM230",
            [
                "sensor.device_apparent_power",
                "sensor.device_current",
                "sensor.device_frequency",
                "sensor.device_power_factor",
                "sensor.device_reactive_power",
                "sensor.device_voltage",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "SDM630",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_frequency",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-KWH1",
            [
                "sensor.device_apparent_power",
                "sensor.device_current",
                "sensor.device_frequency",
                "sensor.device_power_factor",
                "sensor.device_reactive_power",
                "sensor.device_voltage",
                "sensor.device_wi_fi_strength",
            ],
        ),
        (
            "HWE-KWH3",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_frequency",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_wi_fi_strength",
            ],
        ),
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default sensors."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (entry := entity_registry.async_get(entity_id))
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("exception", [RequestError])
async def test_sensors_unreachable(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
) -> None:
    """Test sensor handles API unreachable."""
    assert (state := hass.states.get("sensor.device_energy_import_tariff_1"))
    assert state.state == "10830.511"

    mock_homewizardenergy.data.side_effect = exception
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_external_sensors_unreachable(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test external device sensor handles API unreachable."""
    assert (state := hass.states.get("sensor.gas_meter_gas"))
    assert state.state == "111.111"

    mock_homewizardenergy.data.return_value = Data.from_dict({})
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-SKT-11",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_factor",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_voltage",
                "sensor.device_water_usage",
            ],
        ),
        (
            "HWE-SKT-21",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_water_usage",
            ],
        ),
        (
            "HWE-WTR",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_apparent_power",
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_current",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_export",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_energy_import",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_factor",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_1",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_power",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_reactive_power",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_voltage",
            ],
        ),
        (
            "SDM230",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_average_demand",
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_water_usage",
            ],
        ),
        (
            "SDM630",
            [
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_failures_detected",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_voltage",
                "sensor.device_water_usage",
            ],
        ),
        (
            "HWE-KWH1",
            [
                "sensor.device_apparent_power_phase_1",
                "sensor.device_apparent_power_phase_2",
                "sensor.device_apparent_power_phase_3",
                "sensor.device_average_demand",
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_factor_phase_1",
                "sensor.device_power_factor_phase_2",
                "sensor.device_power_factor_phase_3",
                "sensor.device_power_failures_detected",
                "sensor.device_power_phase_2",
                "sensor.device_power_phase_3",
                "sensor.device_reactive_power_phase_1",
                "sensor.device_reactive_power_phase_2",
                "sensor.device_reactive_power_phase_3",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_water_usage",
            ],
        ),
        (
            "HWE-KWH3",
            [
                "sensor.device_average_demand",
                "sensor.device_current_phase_1",
                "sensor.device_current_phase_2",
                "sensor.device_current_phase_3",
                "sensor.device_dsmr_version",
                "sensor.device_energy_export_tariff_1",
                "sensor.device_energy_export_tariff_2",
                "sensor.device_energy_export_tariff_3",
                "sensor.device_energy_export_tariff_4",
                "sensor.device_energy_import_tariff_1",
                "sensor.device_energy_import_tariff_2",
                "sensor.device_energy_import_tariff_3",
                "sensor.device_energy_import_tariff_4",
                "sensor.device_frequency",
                "sensor.device_long_power_failures_detected",
                "sensor.device_peak_demand_current_month",
                "sensor.device_power_failures_detected",
                "sensor.device_smart_meter_identifier",
                "sensor.device_smart_meter_model",
                "sensor.device_tariff",
                "sensor.device_total_water_usage",
                "sensor.device_voltage_phase_1",
                "sensor.device_voltage_phase_2",
                "sensor.device_voltage_phase_3",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_voltage",
                "sensor.device_water_usage",
            ],
        ),
    ],
)
async def test_entities_not_created_for_device(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> None:
    """Ensures entities for a specific device are not created."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)


async def test_gas_meter_migrated(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test old gas meter sensor is migrated."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "aabbccddeeff_total_gas_m3",
    )

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.homewizard_aabbccddeeff_total_gas_m3"

    assert (entity_entry := entity_registry.async_get(entity_id))
    assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

    # Make really sure this happens
    assert entity_entry.previous_unique_id == "aabbccddeeff_total_gas_m3"


async def test_gas_unique_id_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test old gas meter id sensor is removed."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "aabbccddeeff_gas_unique_id",
    )

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.homewizard_aabbccddeeff_gas_unique_id"

    assert not entity_registry.async_get(entity_id)
