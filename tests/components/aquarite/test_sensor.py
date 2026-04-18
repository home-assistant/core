"""Tests for Aquarite sensor entity native_value and platform setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aquarite.sensor import (
    AquariteHydrolyserSensorEntity,
    AquaritePoolNameSensorEntity,
    AquariteRssiSensorEntity,
    AquariteRxValueSensorEntity,
    AquariteTemperatureSensorEntity,
    AquariteTimeSensorEntity,
    AquariteValueSensorEntity,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

# ── Helpers ─────────────────────────────────────────────────────


def _make_coordinator(
    data: dict[str, Any], pool_id: str = MOCK_POOL_ID, pool_name: str = MOCK_POOL_NAME
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


# ── Temperature sensor ──────────────────────────────────────────


def test_temperature_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test native_value returns raw float from coordinator."""
    with _patch_entity_init():
        entity = AquariteTemperatureSensorEntity(
            mock_coordinator, "temperature", "main.temperature"
        )
    assert entity.native_value == 25.5


def test_temperature_native_value_missing() -> None:
    """Test native_value returns None when path is missing."""
    coord = _make_coordinator({"main": {}})
    with _patch_entity_init():
        entity = AquariteTemperatureSensorEntity(
            coord, "temperature", "main.temperature"
        )
    assert entity.native_value is None


def test_temperature_native_value_non_numeric() -> None:
    """Test native_value returns None for non-numeric data."""
    coord = _make_coordinator({"main": {"temperature": "not_a_number"}})
    with _patch_entity_init():
        entity = AquariteTemperatureSensorEntity(
            coord, "temperature", "main.temperature"
        )
    assert entity.native_value is None


# ── Value sensor (divides by 100) ───────────────────────────────


def test_value_sensor_native_value_ph(
    mock_coordinator: MagicMock,
) -> None:
    """Test pH value is divided by 100."""
    with _patch_entity_init():
        entity = AquariteValueSensorEntity(mock_coordinator, "ph", "modules.ph.current")
    assert entity.native_value == 7.42


def test_value_sensor_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"modules": {}})
    with _patch_entity_init():
        entity = AquariteValueSensorEntity(coord, "ph", "modules.ph.current")
    assert entity.native_value is None


def test_value_sensor_native_value_non_numeric() -> None:
    """Test value sensor returns None for non-numeric data."""
    coord = _make_coordinator({"modules": {"ph": {"current": "bad"}}})
    with _patch_entity_init():
        entity = AquariteValueSensorEntity(coord, "ph", "modules.ph.current")
    assert entity.native_value is None


# ── Hydrolyser sensor (divides by 10) ──────────────────────────


def test_hydrolyser_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test hydrolyser value is divided by 10."""
    with _patch_entity_init():
        entity = AquariteHydrolyserSensorEntity(
            mock_coordinator, "electrolysis", "hidro.current"
        )
    assert entity.native_value == 5.0


def test_hydrolyser_native_value_non_numeric() -> None:
    """Test returns None for non-numeric data."""
    coord = _make_coordinator({"hidro": {"current": "bad"}})
    with _patch_entity_init():
        entity = AquariteHydrolyserSensorEntity(coord, "electrolysis", "hidro.current")
    assert entity.native_value is None


# ── Rx sensor (integer, no scaling) ─────────────────────────────


def test_rx_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test Rx value is returned as integer."""
    with _patch_entity_init():
        entity = AquariteRxValueSensorEntity(
            mock_coordinator, "rx", "modules.rx.current"
        )
    assert entity.native_value == 707


def test_rx_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"modules": {}})
    with _patch_entity_init():
        entity = AquariteRxValueSensorEntity(coord, "rx", "modules.rx.current")
    assert entity.native_value is None


def test_rx_native_value_non_numeric() -> None:
    """Test Rx sensor returns None for non-numeric data."""
    coord = _make_coordinator({"modules": {"rx": {"current": "bad"}}})
    with _patch_entity_init():
        entity = AquariteRxValueSensorEntity(coord, "rx", "modules.rx.current")
    assert entity.native_value is None


# ── Time sensor (divides by 60) ─────────────────────────────────


def test_time_sensor_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test time value is divided by 60 to return hours."""
    with _patch_entity_init():
        entity = AquariteTimeSensorEntity(
            mock_coordinator, "filtration_intel_time", "filtration.intel.time"
        )
    assert entity.native_value == 10.0


def test_time_sensor_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"filtration": {}})
    with _patch_entity_init():
        entity = AquariteTimeSensorEntity(
            coord, "filtration_intel_time", "filtration.intel.time"
        )
    assert entity.native_value is None


def test_time_sensor_native_value_non_numeric() -> None:
    """Test time sensor returns None for non-numeric data."""
    coord = _make_coordinator({"filtration": {"intel": {"time": "bad"}}})
    with _patch_entity_init():
        entity = AquariteTimeSensorEntity(
            coord, "filtration_intel_time", "filtration.intel.time"
        )
    assert entity.native_value is None


# ── RSSI sensor ─────────────────────────────────────────────────


def test_rssi_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test RSSI value is returned as integer."""
    with _patch_entity_init():
        entity = AquariteRssiSensorEntity(mock_coordinator)
    assert entity.native_value == -65


def test_rssi_native_value_missing() -> None:
    """Test returns None when RSSI is missing."""
    coord = _make_coordinator({"main": {}})
    with _patch_entity_init():
        entity = AquariteRssiSensorEntity(coord)
    assert entity.native_value is None


def test_rssi_native_value_non_numeric() -> None:
    """Test RSSI sensor returns None for non-numeric data."""
    coord = _make_coordinator({"main": {"RSSI": "bad"}})
    with _patch_entity_init():
        entity = AquariteRssiSensorEntity(coord)
    assert entity.native_value is None


# ── Pool name sensor ────────────────────────────────────────────


def test_pool_name_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test pool name sensor returns the pool name."""
    with _patch_entity_init():
        entity = AquaritePoolNameSensorEntity(mock_coordinator)
    assert entity.native_value == MOCK_POOL_NAME


# ── Platform setup ──────────────────────────────────────────────


async def _setup_sensor_platform(
    hass: HomeAssistant, coordinators: list[MagicMock]
) -> list:
    """Set up the sensor platform with pre-built coordinators; capture entities."""
    entry = MagicMock()
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinators = {c.pool_id: c for c in coordinators}

    captured: list = []

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

    translation_keys = {e._attr_translation_key for e in entities}
    # Always-on entities
    assert "temperature" in translation_keys
    assert "rssi" in translation_keys
    assert "filtration_intel_time" in translation_keys
    assert "pool_name" in translation_keys
    # Module-gated (fixture has hasPH=1, hasRX=1, hasHidro=1 with is_electrolysis=True)
    assert "ph" in translation_keys
    assert "rx" in translation_keys
    assert "electrolysis" in translation_keys
    # Disabled modules in fixture
    assert "cd" not in translation_keys
    assert "cl" not in translation_keys
    assert "uv" not in translation_keys


async def test_async_setup_entry_hydrolysis_branch(hass: HomeAssistant) -> None:
    """Test the hydrolysis (non-electrolysis) branch."""
    data = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"is_electrolysis": False, "current": 50},
        "form": {},
    }
    coord = _make_coordinator(data)
    entities = await _setup_sensor_platform(hass, [coord])
    translation_keys = {e._attr_translation_key for e in entities}
    assert "hydrolysis" in translation_keys
    assert "electrolysis" not in translation_keys


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
        "form": {},
    }
    coord = _make_coordinator(data)
    entities = await _setup_sensor_platform(hass, [coord])
    translation_keys = {e._attr_translation_key for e in entities}
    assert {"cd", "cl", "ph", "rx", "uv", "electrolysis"} <= translation_keys


async def test_async_setup_entry_multi_pool(
    hass: HomeAssistant, mock_pool_data: dict[str, Any]
) -> None:
    """Test setup creates entities for every pool on the account."""
    coord_a = _make_coordinator(mock_pool_data, pool_id="pool_a", pool_name="Pool A")
    coord_b = _make_coordinator(mock_pool_data, pool_id="pool_b", pool_name="Pool B")
    entities = await _setup_sensor_platform(hass, [coord_a, coord_b])

    # Every entity should have a unique_id prefixed with its pool_id
    pool_a_ids = {e._attr_unique_id for e in entities if "pool_a-" in e._attr_unique_id}
    pool_b_ids = {e._attr_unique_id for e in entities if "pool_b-" in e._attr_unique_id}
    assert pool_a_ids
    assert pool_b_ids
    # Same count of entities per pool
    assert len(pool_a_ids) == len(pool_b_ids)
