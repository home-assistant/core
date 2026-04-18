"""Tests for Aquarite sensor entity native_value and platform setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aquarite.sensor import (
    SENSOR_DESCRIPTIONS,
    AquariteSensorEntity,
    AquariteSensorEntityDescription,
    _convert_tenths,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

# ── Helpers ─────────────────────────────────────────────────────


def _make_coordinator(
    data: dict[str, Any],
    pool_id: str = MOCK_POOL_ID,
    pool_name: str = MOCK_POOL_NAME,
) -> MagicMock:
    """Build a mock coordinator that resolves dot-notation paths."""

    def _get_value(path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current: Any = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    coord = MagicMock()
    coord.data = data
    coord.pool_id = pool_id
    coord.pool_name = pool_name
    coord.get_value = MagicMock(side_effect=_get_value)
    return coord


@pytest.fixture
def mock_coordinator(mock_pool_data: dict[str, Any]) -> MagicMock:
    """Return a mock coordinator backed by the standard pool fixture."""
    return _make_coordinator(mock_pool_data)


def _patch_entity_init():
    """Patch CoordinatorEntity.__init__ to skip hass wiring."""
    return patch(
        "homeassistant.helpers.update_coordinator.CoordinatorEntity.__init__",
        lambda self, coordinator, context=None: setattr(
            self, "coordinator", coordinator
        ),
    )


def _get_description(key: str) -> AquariteSensorEntityDescription:
    """Look up a sensor description by key."""
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise ValueError(f"No description for key={key}")


def _make_entity(coordinator: MagicMock, key: str) -> AquariteSensorEntity:
    """Build an AquariteSensorEntity for the given description key."""
    with _patch_entity_init():
        return AquariteSensorEntity(coordinator, _get_description(key))


# ── Temperature sensor ──────────────────────────────────────────


def test_temperature_native_value(mock_coordinator: MagicMock) -> None:
    """Test native_value returns raw float from coordinator."""
    entity = _make_entity(mock_coordinator, "temperature")
    assert entity.native_value == 25.5


def test_temperature_native_value_missing() -> None:
    """Test native_value returns None when path is missing."""
    entity = _make_entity(_make_coordinator({"main": {}}), "temperature")
    assert entity.native_value is None


def test_temperature_native_value_non_numeric() -> None:
    """Test native_value returns None for non-numeric data."""
    entity = _make_entity(
        _make_coordinator({"main": {"temperature": "bad"}}), "temperature"
    )
    assert entity.native_value is None


# ── Value sensor (divides by 100) ───────────────────────────────


def test_ph_native_value(mock_coordinator: MagicMock) -> None:
    """Test pH value is divided by 100."""
    entity = _make_entity(mock_coordinator, "ph")
    assert entity.native_value == 7.42


def test_ph_native_value_missing() -> None:
    """Test returns None when path is absent."""
    entity = _make_entity(_make_coordinator({"modules": {}}), "ph")
    assert entity.native_value is None


def test_ph_native_value_non_numeric() -> None:
    """Test returns None for non-numeric data."""
    entity = _make_entity(
        _make_coordinator({"modules": {"ph": {"current": "bad"}}}), "ph"
    )
    assert entity.native_value is None


# ── Hydrolyser sensor (dynamic key) ────────────────────────────


def test_hydrolyser_native_value(mock_coordinator: MagicMock) -> None:
    """Test hydrolyser value is divided by 10."""
    desc = AquariteSensorEntityDescription(
        key="electrolysis",
        translation_key="electrolysis",
        native_unit_of_measurement="g/h",
        value_path="hidro.current",
        value_fn=_convert_tenths,
    )
    with _patch_entity_init():
        entity = AquariteSensorEntity(mock_coordinator, desc)
    assert entity.native_value == 5.0


# ── Rx sensor (integer) ────────────────────────────────────────


def test_rx_native_value(mock_coordinator: MagicMock) -> None:
    """Test Rx value is returned as integer."""
    entity = _make_entity(mock_coordinator, "rx")
    assert entity.native_value == 707


def test_rx_native_value_missing() -> None:
    """Test returns None when path is absent."""
    entity = _make_entity(_make_coordinator({"modules": {}}), "rx")
    assert entity.native_value is None


def test_rx_native_value_non_numeric() -> None:
    """Test Rx sensor returns None for non-numeric data."""
    entity = _make_entity(
        _make_coordinator({"modules": {"rx": {"current": "bad"}}}), "rx"
    )
    assert entity.native_value is None


# ── Time sensor (divides by 60) ─────────────────────────────────


def test_time_sensor_native_value(mock_coordinator: MagicMock) -> None:
    """Test time value is divided by 60 to return hours."""
    entity = _make_entity(mock_coordinator, "filtration_intel_time")
    assert entity.native_value == 10.0


def test_time_sensor_native_value_missing() -> None:
    """Test returns None when path is absent."""
    entity = _make_entity(
        _make_coordinator({"filtration": {}}), "filtration_intel_time"
    )
    assert entity.native_value is None


def test_time_sensor_native_value_non_numeric() -> None:
    """Test time sensor returns None for non-numeric data."""
    entity = _make_entity(
        _make_coordinator({"filtration": {"intel": {"time": "bad"}}}),
        "filtration_intel_time",
    )
    assert entity.native_value is None


# ── RSSI sensor ─────────────────────────────────────────────────


def test_rssi_native_value(mock_coordinator: MagicMock) -> None:
    """Test RSSI value is returned as integer."""
    entity = _make_entity(mock_coordinator, "rssi")
    assert entity.native_value == -65


def test_rssi_native_value_missing() -> None:
    """Test returns None when RSSI is missing."""
    entity = _make_entity(_make_coordinator({"main": {}}), "rssi")
    assert entity.native_value is None


def test_rssi_native_value_non_numeric() -> None:
    """Test RSSI sensor returns None for non-numeric data."""
    entity = _make_entity(_make_coordinator({"main": {"RSSI": "bad"}}), "rssi")
    assert entity.native_value is None


# ── Pool name sensor ────────────────────────────────────────────


def test_pool_name_native_value(mock_coordinator: MagicMock) -> None:
    """Test pool name sensor returns the pool name."""
    entity = _make_entity(mock_coordinator, "pool_name")
    assert entity.native_value == MOCK_POOL_NAME


# ── Platform setup ──────────────────────────────────────────────


async def _setup_sensor_platform(
    hass: HomeAssistant, coordinators: list[MagicMock]
) -> list[AquariteSensorEntity]:
    """Set up the sensor platform with pre-built coordinators; capture entities."""
    entry = MagicMock()
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinators = {c.pool_id: c for c in coordinators}

    captured: list[AquariteSensorEntity] = []

    def _add_entities(entities: list, *_args: Any, **_kwargs: Any) -> None:
        captured.extend(entities)

    with _patch_entity_init():
        await async_setup_entry(hass, entry, _add_entities)
    return captured


async def test_async_setup_entry_full_modules(
    hass: HomeAssistant, mock_pool_data: dict[str, Any]
) -> None:
    """Test setup creates entities for every module flagged as present."""
    coord = _make_coordinator(mock_pool_data)
    entities = await _setup_sensor_platform(hass, [coord])

    keys = {e.entity_description.key for e in entities}
    # Always-on entities
    assert "temperature" in keys
    assert "rssi" in keys
    assert "filtration_intel_time" in keys
    assert "pool_name" in keys
    # Module-gated (fixture has hasPH=1, hasRX=1, hasHidro=1+is_electrolysis=True)
    assert "ph" in keys
    assert "rx" in keys
    assert "electrolysis" in keys
    # Disabled modules in fixture
    assert "cd" not in keys
    assert "cl" not in keys
    assert "uv" not in keys


async def test_async_setup_entry_hydrolysis_branch(hass: HomeAssistant) -> None:
    """Test the hydrolysis (non-electrolysis) branch."""
    data = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"is_electrolysis": False, "current": 50},
    }
    coord = _make_coordinator(data)
    entities = await _setup_sensor_platform(hass, [coord])
    keys = {e.entity_description.key for e in entities}
    assert "hydrolysis" in keys
    assert "electrolysis" not in keys


async def test_async_setup_entry_all_modules_enabled(hass: HomeAssistant) -> None:
    """Test setup when every module flag is enabled."""
    data = {
        "main": {
            "hasCD": 1,
            "hasCL": 1,
            "hasPH": 1,
            "hasRX": 1,
            "hasUV": 1,
            "hasHidro": 1,
            "version": 1,
        },
        "hidro": {"is_electrolysis": True, "current": 50},
    }
    coord = _make_coordinator(data)
    entities = await _setup_sensor_platform(hass, [coord])
    keys = {e.entity_description.key for e in entities}
    assert {"cd", "cl", "ph", "rx", "uv", "electrolysis"} <= keys


async def test_async_setup_entry_multi_pool(
    hass: HomeAssistant, mock_pool_data: dict[str, Any]
) -> None:
    """Test setup creates entities for every pool on the account."""
    coord_a = _make_coordinator(mock_pool_data, pool_id="pool_a", pool_name="Pool A")
    coord_b = _make_coordinator(mock_pool_data, pool_id="pool_b", pool_name="Pool B")
    entities = await _setup_sensor_platform(hass, [coord_a, coord_b])

    pool_a_ids = {e._attr_unique_id for e in entities if "pool_a-" in e._attr_unique_id}
    pool_b_ids = {e._attr_unique_id for e in entities if "pool_b-" in e._attr_unique_id}
    assert pool_a_ids
    assert pool_b_ids
    assert len(pool_a_ids) == len(pool_b_ids)
