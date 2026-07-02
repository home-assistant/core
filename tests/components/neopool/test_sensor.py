"""Tests for the NeoPool sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.neopool.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_measurement_sensors_suppressed_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Probe sensors report unknown while filtration pump is off (stale reading)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["Filtration Pump"] = False
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    for entity_id in (
        "sensor.neopool_ph_level",
        "sensor.neopool_redox_potential",
        "sensor.neopool_water_temperature",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not registered"
        assert state.state == "unknown"


async def test_production_sensors_zero_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Production sensors report 0 while filtration pump is off (cell idle)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["Filtration Pump"] = False
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    for entity_id in (
        "sensor.neopool_hydrolysis_intensity",
        "sensor.neopool_ionization_level",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not registered"
        assert state.state == "0"


@pytest.mark.parametrize(
    ("filt_mode", "expected"),
    [
        (0, "manual"),
        (1, "auto"),
        (2, "heating"),
        (3, "smart"),
        (4, "intelligent"),
        (13, "backwash"),
    ],
)
async def test_filt_mode_native_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    filt_mode: int,
    expected: str,
) -> None:
    """Filt mode native value reads the lib's decoded filtration_mode key."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["MBF_PAR_FILT_MODE"] = filt_mode
    coordinator.data["filtration_mode"] = expected
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_filtration_mode")
    assert state is not None
    assert state.state == expected


async def test_ph_pump_status_options_per_relay_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The pH pump status options list shrinks based on the relay configuration."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["MBF_PAR_RELAY_PH"] = 1
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_ph_pump_status")
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["off", "idle", "acid"]

    coordinator.data["MBF_PAR_RELAY_PH"] = 2
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_ph_pump_status")
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["off", "idle", "base"]

    coordinator.data["MBF_PAR_RELAY_PH"] = 0
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_ph_pump_status")
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["off", "idle", "acid", "base", "both"]


async def test_hidro_current_g_per_hour_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """In g/h mode HIDRO_CURRENT swaps unit and bumps display precision."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["MBF_PAR_UICFG_MACHINE"] = 1
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.neopool_hydrolysis_intensity")
    assert state is not None
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "g/h"


_CELL_RUNTIME_ENTITY_IDS: dict[str, str] = {
    "CELL_RUNTIME_TOTAL": "sensor.neopool_cell_runtime_total",
    "CELL_RUNTIME_PART": "sensor.neopool_cell_runtime_since_reset",
    "CELL_RUNTIME_POLA": "sensor.neopool_cell_runtime_in_polarity_1",
    "CELL_RUNTIME_POLB": "sensor.neopool_cell_runtime_in_polarity_2",
    "CELL_RUNTIME_POL_CHANGES": "sensor.neopool_cell_polarity_changes",
}


@pytest.mark.parametrize(
    ("key", "expected_seconds"),
    [
        ("CELL_RUNTIME_TOTAL", 65536),
        ("CELL_RUNTIME_PART", 3600),
        ("CELL_RUNTIME_POLA", 1800),
        ("CELL_RUNTIME_POLB", 1800),
        ("CELL_RUNTIME_POL_CHANGES", 7),
    ],
)
async def test_cell_runtime_sensor_reads_combined_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    key: str,
    expected_seconds: int,
) -> None:
    """Each CELL_RUNTIME_* sensor reads the combined u32 key from coordinator data.

    All five sensors have ``entity_registry_enabled_default=False``; we set up
    the integration first, enable the specific entity in the registry, and
    reload the entry so the platform re-creates it as an active entity.
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = _CELL_RUNTIME_ENTITY_IDS[key]
    registry = er.async_get(hass)
    registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} not registered"
    # POL_CHANGES has no unit; the others declare seconds but suggest hours,
    # so state.state is expressed in hours (converted by the frontend layer).
    if key == "CELL_RUNTIME_POL_CHANGES":
        assert state.state == str(expected_seconds)
    else:
        assert float(state.state) == pytest.approx(expected_seconds / 3600, abs=1e-4)


async def test_cell_runtime_default_disabled_state() -> None:
    """All five cell-runtime sensors default to disabled."""
    for key in (
        "CELL_RUNTIME_TOTAL",
        "CELL_RUNTIME_PART",
        "CELL_RUNTIME_POLA",
        "CELL_RUNTIME_POLB",
        "CELL_RUNTIME_POL_CHANGES",
    ):
        assert SENSOR_DESCRIPTIONS[key].entity_registry_enabled_default is False


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Snapshot every entity registered by the sensor platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    entries = sorted(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id),
        key=lambda e: e.entity_id,
    )
    assert entries == snapshot


async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client_minimal: MagicMock,
) -> None:
    """Snapshot the sensor entities registered when no modules are present."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    entries = sorted(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id),
        key=lambda e: e.entity_id,
    )
    assert entries == snapshot
