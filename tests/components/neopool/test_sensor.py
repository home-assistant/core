"""Tests for the NeoPool sensor platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from neopool_modbus.decoders import (
    decode_hidro_polarity,
    decode_ion_polarity,
    decode_ph_pump_status,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.neopool.const import DOMAIN
from homeassistant.components.neopool.sensor import SENSOR_DESCRIPTIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform as ep, entity_registry as er

from . import setup_integration
from .conftest import MOCK_SERIAL

from tests.common import MockConfigEntry


def _sensor_by_key(hass: HomeAssistant, key: str):
    """Return the live sensor entity object for a given _key, or None."""
    for platforms in ep.async_get_platforms(hass, "neopool"):
        for ent in platforms.entities.values():
            if (
                ent.entity_id.startswith("sensor.")
                and getattr(ent, "_key", None) == key
            ):
                return ent
    return None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        ({"pH acid pump active": True}, None),
        (
            {
                "pH control module": False,
                "pH acid pump active": False,
                "pH pump active": False,
            },
            "off",
        ),
        (
            {
                "pH control module": True,
                "MBF_PAR_RELAY_PH": 1,
                "pH pump active": True,
                "pH acid pump active": False,
            },
            "acid",
        ),
        (
            {
                "pH control module": True,
                "MBF_PAR_RELAY_PH": 1,
                "pH pump active": False,
                "pH acid pump active": False,
            },
            "idle",
        ),
        (
            {
                "pH control module": True,
                "MBF_PAR_RELAY_PH": 2,
                "pH pump active": True,
                "pH acid pump active": False,
            },
            "base",
        ),
        (
            {
                "pH control module": True,
                "MBF_PAR_RELAY_PH": 0,
                "pH pump active": True,
                "pH acid pump active": True,
            },
            "both",
        ),
    ],
)
async def test_ph_pump_status_decoder(
    data: dict[str, Any],
    expected: str | None,
) -> None:
    """decode_ph_pump_status covers every relay_ph branch."""
    assert decode_ph_pump_status(data) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        (
            {
                "HIDRO in Pol1": False,
                "HIDRO in Pol2": False,
                "HIDRO in dead time": False,
                "Filtration Pump": False,
            },
            "off",
        ),
        (
            {"HIDRO in Pol1": True, "HIDRO in Pol2": False, "HIDRO in dead time": True},
            "dead_time",
        ),
        (
            {
                "HIDRO in Pol1": True,
                "HIDRO in Pol2": False,
                "HIDRO in dead time": False,
            },
            "pol1",
        ),
        (
            {
                "HIDRO in Pol1": False,
                "HIDRO in Pol2": True,
                "HIDRO in dead time": False,
            },
            "pol2",
        ),
    ],
)
async def test_hidro_polarity_decoder(
    data: dict[str, Any],
    expected: str | None,
) -> None:
    """decode_hidro_polarity covers every polarity / flow branch."""
    assert decode_hidro_polarity(data) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        (
            {"ION in Pol1": True, "ION in Pol2": False, "ION in dead time": True},
            "dead_time",
        ),
        (
            {"ION in Pol1": True, "ION in Pol2": False, "ION in dead time": False},
            "pol1",
        ),
        (
            {"ION in Pol1": False, "ION in Pol2": True, "ION in dead time": False},
            "pol2",
        ),
        (
            {"ION in Pol1": False, "ION in Pol2": False, "ION in dead time": False},
            "off",
        ),
    ],
)
async def test_ion_polarity_decoder(
    data: dict[str, Any],
    expected: str | None,
) -> None:
    """decode_ion_polarity covers every branch."""
    assert decode_ion_polarity(data) == expected


async def test_measurement_sensors_suppressed_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Probe sensors report None while filtration pump is off (stale reading)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["Filtration Pump"] = False
    for key in (
        "MBF_MEASURE_PH",
        "MBF_MEASURE_RX",
        "MBF_MEASURE_TEMPERATURE",
    ):
        entity = _sensor_by_key(hass, key)
        if entity is None:
            continue
        assert entity.native_value is None


async def test_production_sensors_zero_when_filtration_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Production sensors report 0 while filtration pump is off (cell idle)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.data["Filtration Pump"] = False
    for key in ("MBF_HIDRO_CURRENT", "MBF_HIDRO_VOLTAGE", "MBF_ION_CURRENT"):
        entity = _sensor_by_key(hass, key)
        if entity is None:
            continue
        assert entity.native_value == 0


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
    entity = _sensor_by_key(hass, "MBF_PAR_FILT_MODE")
    assert entity is not None
    coordinator = mock_config_entry.runtime_data
    coordinator.data["MBF_PAR_FILT_MODE"] = filt_mode
    coordinator.data["filtration_mode"] = expected
    assert entity.native_value == expected


async def test_ph_pump_status_options_per_relay_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The pH pump status options list shrinks based on the relay configuration."""
    await setup_integration(hass, mock_config_entry)
    entity = _sensor_by_key(hass, "PH_PUMP_STATUS")
    if entity is None:
        pytest.skip("PH_PUMP_STATUS entity not registered")
    coordinator = mock_config_entry.runtime_data
    coordinator.data["MBF_PAR_RELAY_PH"] = 1
    assert entity.options == ["off", "idle", "acid"]
    coordinator.data["MBF_PAR_RELAY_PH"] = 2
    assert entity.options == ["off", "idle", "base"]
    coordinator.data["MBF_PAR_RELAY_PH"] = 0
    assert entity.options == ["off", "idle", "acid", "base", "both"]


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

    entity = _sensor_by_key(hass, "MBF_HIDRO_CURRENT")
    if entity is None:
        pytest.skip("MBF_HIDRO_CURRENT entity not registered on this fixture")
    assert entity.suggested_display_precision == 1
    assert entity.native_unit_of_measurement == "g/h"


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

    All five sensors have ``entity_registry_enabled_default=False``; HA skips
    constructing entity objects for disabled-by-default keys, so we
    pre-register them as enabled in the entity_registry.
    """
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_SERIAL}_{key.lower()}",
        config_entry=mock_config_entry,
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)
    entity = _sensor_by_key(hass, key)
    assert entity is not None, f"{key} sensor was not registered"
    assert entity.native_value == expected_seconds


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
