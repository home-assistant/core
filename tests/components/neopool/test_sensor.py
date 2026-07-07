"""Tests for the NeoPool sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import ATTR_OPTIONS
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_measurement_sensors_suppressed_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Probe sensors report unknown while filtration pump is off (stale reading)."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    for entity_id in (
        "sensor.neopool_ph",
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Production sensors report 0 while filtration pump is off (cell idle)."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "Filtration Pump": False,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
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
    freezer: FrozenDateTimeFactory,
    filt_mode: int,
    expected: str,
) -> None:
    """Filt mode native value reads the lib's decoded filtration_mode key."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_FILT_MODE": filt_mode,
        "filtration_mode": expected,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_filtration_mode")
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("relay", "expected_options"),
    [
        pytest.param(1, ["off", "idle", "acid"], id="acid_only"),
        pytest.param(2, ["off", "idle", "base"], id="base_only"),
        pytest.param(0, ["off", "idle", "acid", "base", "both"], id="both_relays"),
    ],
)
async def test_ph_pump_status_options_per_relay_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    relay: int,
    expected_options: list[str],
) -> None:
    """The pH pump status options list shrinks based on the relay configuration."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_RELAY_PH": relay,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.neopool_ph_pump_status")
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == expected_options


async def test_hidro_current_g_per_hour_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """In g/h mode HIDRO_CURRENT swaps unit and bumps display precision."""
    await setup_integration(hass, mock_config_entry)
    mock_neopool_client.async_read_all.return_value = {
        **MOCK_POOL_DATA,
        "MBF_PAR_UICFG_MACHINE": 1,
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
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
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_cell_runtime_duration_sensor_reads_combined_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    key: str,
    expected_seconds: int,
) -> None:
    """Each duration CELL_RUNTIME_* sensor reads the combined u32 key from coordinator data.

    Sensors have ``entity_registry_enabled_default=False``; enabling every
    disabled-by-default entity via the fixture avoids the reload dance. The
    sensors declare seconds but suggest hours, so ``state.state`` is expressed
    in hours (converted by the frontend layer).
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = _CELL_RUNTIME_ENTITY_IDS[key]
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} not registered"
    assert float(state.state) == pytest.approx(expected_seconds / 3600, abs=1e-4)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_cell_runtime_pol_changes_sensor_reads_combined_register(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """CELL_RUNTIME_POL_CHANGES reads the combined u32 key as a raw counter.

    Unlike the duration sensors, this one has no unit and no unit conversion,
    so ``state.state`` is the raw integer from coordinator data.
    """
    await setup_integration(hass, mock_config_entry)

    entity_id = _CELL_RUNTIME_ENTITY_IDS["CELL_RUNTIME_POL_CHANGES"]
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} not registered"
    assert state.state == "7"


@pytest.mark.freeze_time("2026-07-03T12:00:00Z")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the sensor platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2026-07-03T12:00:00Z")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the sensor entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
