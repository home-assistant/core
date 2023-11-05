"""Test sensor entity for HomeWizard."""

from unittest.mock import MagicMock

from homewizard_energy.errors import DisabledError, RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homewizard.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

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
                "sensor.device_dsmr_version",
                "sensor.device_smart_meter_model",
                "sensor.device_smart_meter_identifier",
                "sensor.device_wi_fi_ssid",
                "sensor.device_active_tariff",
                "sensor.device_wi_fi_strength",
                "sensor.device_total_energy_import",
                "sensor.device_total_energy_import_tariff_1",
                "sensor.device_total_energy_import_tariff_2",
                "sensor.device_total_energy_import_tariff_3",
                "sensor.device_total_energy_import_tariff_4",
                "sensor.device_total_energy_export",
                "sensor.device_total_energy_export_tariff_1",
                "sensor.device_total_energy_export_tariff_2",
                "sensor.device_total_energy_export_tariff_3",
                "sensor.device_total_energy_export_tariff_4",
                "sensor.device_active_power",
                "sensor.device_active_power_phase_1",
                "sensor.device_active_power_phase_2",
                "sensor.device_active_power_phase_3",
                "sensor.device_active_voltage_phase_1",
                "sensor.device_active_voltage_phase_2",
                "sensor.device_active_voltage_phase_3",
                "sensor.device_active_current_phase_1",
                "sensor.device_active_current_phase_2",
                "sensor.device_active_current_phase_3",
                "sensor.device_active_frequency",
                "sensor.device_voltage_sags_detected_phase_1",
                "sensor.device_voltage_sags_detected_phase_2",
                "sensor.device_voltage_sags_detected_phase_3",
                "sensor.device_voltage_swells_detected_phase_1",
                "sensor.device_voltage_swells_detected_phase_2",
                "sensor.device_voltage_swells_detected_phase_3",
                "sensor.device_power_failures_detected",
                "sensor.device_long_power_failures_detected",
                "sensor.device_active_average_demand",
                "sensor.device_peak_demand_current_month",
                "sensor.device_total_gas",
                "sensor.device_gas_meter_identifier",
                "sensor.device_active_water_usage",
                "sensor.device_total_water_usage",
            ],
        )
    ],
)
async def test_sensors_p1_meter(
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
    "entity_id",
    [
        "sensor.device_wi_fi_strength",
        "sensor.device_active_voltage_phase_1",
        "sensor.device_active_voltage_phase_2",
        "sensor.device_active_voltage_phase_3",
        "sensor.device_active_current_phase_1",
        "sensor.device_active_current_phase_2",
        "sensor.device_active_current_phase_3",
        "sensor.device_active_frequency",
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default sensors."""
    assert not hass.states.get(entity_id)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_fixture", ["HWE-P1-unused-exports"])
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.device_total_energy_export",
        "sensor.device_total_energy_export_tariff_1",
        "sensor.device_total_energy_export_tariff_2",
        "sensor.device_total_energy_export_tariff_3",
        "sensor.device_total_energy_export_tariff_4",
    ],
)
async def test_disabled_by_default_sensors_when_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test the disabled by default unused sensors."""
    assert not hass.states.get(entity_id)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("exception", [RequestError, DisabledError])
async def test_sensors_unreachable(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
) -> None:
    """Test sensor handles API unreachable."""
    assert (state := hass.states.get("sensor.device_total_energy_import_tariff_1"))
    assert state.state == "10830.511"

    mock_homewizardenergy.data.side_effect = exception
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE
