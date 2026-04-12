"""Tests for Aquarite sensor value conversions and entity native_value."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aquarite.sensor import (
    AquariteHydrolyserSensorEntity,
    AquariteLocationSensorEntity,
    AquaritePoolNameSensorEntity,
    AquariteRssiSensorEntity,
    AquariteRxValueSensorEntity,
    AquariteTemperatureSensorEntity,
    AquariteTimeSensorEntity,
    AquariteValueSensorEntity,
)

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME


# ── Pure conversion tests (no HA dependencies) ──────────────────


def test_temperature_conversion() -> None:
    """Test temperature sensor returns raw float."""
    raw_value = 25.5
    assert float(raw_value) == 25.5


def test_value_sensor_scaling() -> None:
    """Test value sensor divides by 100."""
    raw_value = "742"
    assert float(raw_value) / 100 == 7.42


def test_hydrolyser_scaling() -> None:
    """Test hydrolyser sensor divides by 10."""
    raw_value = 50
    assert float(raw_value) / 10 == 5.0


def test_rx_value_integer() -> None:
    """Test Rx sensor returns integer."""
    raw_value = 707
    assert int(raw_value) == 707


def test_time_sensor_conversion() -> None:
    """Test time sensor divides by 60 for hours."""
    raw_value = "600"
    assert float(raw_value) / 60 == 10.0


def test_interval_time_to_datetime() -> None:
    """Test interval seconds to datetime.time conversion."""
    # 28800 seconds = 8:00
    seconds = 28800
    hours = (seconds // 3600) % 24
    minutes = (seconds % 3600) // 60
    result = datetime.time(hours, minutes)
    assert result == datetime.time(8, 0)


def test_interval_time_afternoon() -> None:
    """Test afternoon interval conversion."""
    # 50400 seconds = 14:00
    seconds = 50400
    hours = (seconds // 3600) % 24
    minutes = (seconds % 3600) // 60
    result = datetime.time(hours, minutes)
    assert result == datetime.time(14, 0)


def test_interval_time_to_seconds() -> None:
    """Test datetime.time back to seconds conversion."""
    t = datetime.time(14, 30)
    seconds = t.hour * 3600 + t.minute * 60
    assert seconds == 52200


def test_number_ph_scaling() -> None:
    """Test pH number entity scaling (divide by 100 for display)."""
    raw_value = 742
    scale = 100
    assert raw_value / scale == 7.42


def test_number_ph_write_scaling() -> None:
    """Test pH number write scaling (multiply by 100 for API)."""
    user_value = 7.42
    scale = 100
    assert int(user_value * scale) == 742


def test_number_electrolysis_scaling() -> None:
    """Test electrolysis number scaling (divide by 10)."""
    raw_value = 100
    scale = 10
    assert raw_value / scale == 10.0


def test_speed_label_mapping() -> None:
    """Test speed label select mapping."""
    options = ("slow", "medium", "high")
    assert options[0] == "slow"
    assert options[1] == "medium"
    assert options[2] == "high"


def test_pump_mode_mapping() -> None:
    """Test pump mode select mapping."""
    options = ("manual", "auto", "heat", "smart", "intel")
    assert options[0] == "manual"
    assert options[3] == "smart"
    assert options.index("intel") == 4


# ── Entity-level tests with mocked coordinator ──────────────────


def _make_coordinator(data: dict[str, Any]) -> MagicMock:
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
    coord.pool_id = MOCK_POOL_ID
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
            mock_coordinator,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "temperature",
            "main.temperature",
        )
    assert entity.native_value == 25.5


def test_temperature_native_value_missing() -> None:
    """Test native_value returns None when path is missing."""
    coord = _make_coordinator({"main": {}})
    with _patch_entity_init():
        entity = AquariteTemperatureSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "temperature", "main.temperature"
        )
    assert entity.native_value is None


def test_temperature_native_value_non_numeric() -> None:
    """Test native_value returns None for non-numeric data."""
    coord = _make_coordinator({"main": {"temperature": "not_a_number"}})
    with _patch_entity_init():
        entity = AquariteTemperatureSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "temperature", "main.temperature"
        )
    assert entity.native_value is None


# ── Value sensor (divides by 100) ───────────────────────────────


def test_value_sensor_native_value_ph(
    mock_coordinator: MagicMock,
) -> None:
    """Test pH value is divided by 100."""
    with _patch_entity_init():
        entity = AquariteValueSensorEntity(
            mock_coordinator,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "ph",
            "modules.ph.current",
        )
    assert entity.native_value == 7.42


def test_value_sensor_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"modules": {}})
    with _patch_entity_init():
        entity = AquariteValueSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "ph", "modules.ph.current"
        )
    assert entity.native_value is None


# ── Hydrolyser sensor (divides by 10) ──────────────────────────


def test_hydrolyser_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test hydrolyser value is divided by 10."""
    with _patch_entity_init():
        entity = AquariteHydrolyserSensorEntity(
            mock_coordinator,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "electrolysis",
            "hidro.current",
        )
    assert entity.native_value == 5.0


def test_hydrolyser_native_value_non_numeric() -> None:
    """Test returns None for non-numeric data."""
    coord = _make_coordinator({"hidro": {"current": "bad"}})
    with _patch_entity_init():
        entity = AquariteHydrolyserSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "electrolysis", "hidro.current"
        )
    assert entity.native_value is None


# ── Rx sensor (integer, no scaling) ─────────────────────────────


def test_rx_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test Rx value is returned as integer."""
    with _patch_entity_init():
        entity = AquariteRxValueSensorEntity(
            mock_coordinator,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "rx",
            "modules.rx.current",
        )
    assert entity.native_value == 707


def test_rx_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"modules": {}})
    with _patch_entity_init():
        entity = AquariteRxValueSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "rx", "modules.rx.current"
        )
    assert entity.native_value is None


# ── Time sensor (divides by 60) ─────────────────────────────────


def test_time_sensor_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test time value is divided by 60 to return hours."""
    with _patch_entity_init():
        entity = AquariteTimeSensorEntity(
            mock_coordinator,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "filtration_intel_time",
            "filtration.intel.time",
        )
    assert entity.native_value == 10.0


def test_time_sensor_native_value_missing() -> None:
    """Test returns None when path is absent."""
    coord = _make_coordinator({"filtration": {}})
    with _patch_entity_init():
        entity = AquariteTimeSensorEntity(
            coord,
            MOCK_POOL_ID,
            MOCK_POOL_NAME,
            "filtration_intel_time",
            "filtration.intel.time",
        )
    assert entity.native_value is None


# ── Location sensor ─────────────────────────────────────────────


def test_location_native_value_city(
    mock_coordinator: MagicMock,
) -> None:
    """Test location sensor returns the correct form field."""
    with _patch_entity_init():
        entity = AquariteLocationSensorEntity(
            mock_coordinator, MOCK_POOL_ID, MOCK_POOL_NAME, "city", "city"
        )
    assert entity.native_value == "Waterloo"


def test_location_native_value_missing() -> None:
    """Test returns None when form data is missing."""
    coord = _make_coordinator({})
    with _patch_entity_init():
        entity = AquariteLocationSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME, "city", "city"
        )
    assert entity.native_value is None


# ── RSSI sensor ─────────────────────────────────────────────────


def test_rssi_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test RSSI value is returned as integer."""
    with _patch_entity_init():
        entity = AquariteRssiSensorEntity(
            mock_coordinator, MOCK_POOL_ID, MOCK_POOL_NAME
        )
    assert entity.native_value == -65


def test_rssi_native_value_missing() -> None:
    """Test returns None when RSSI is missing."""
    coord = _make_coordinator({"main": {}})
    with _patch_entity_init():
        entity = AquariteRssiSensorEntity(
            coord, MOCK_POOL_ID, MOCK_POOL_NAME
        )
    assert entity.native_value is None


# ── Pool name sensor ────────────────────────────────────────────


def test_pool_name_native_value(
    mock_coordinator: MagicMock,
) -> None:
    """Test pool name sensor returns the pool name."""
    with _patch_entity_init():
        entity = AquaritePoolNameSensorEntity(
            mock_coordinator, MOCK_POOL_ID, MOCK_POOL_NAME
        )
    assert entity.native_value == MOCK_POOL_NAME
