"""Tests for schema validation and sensor-to-field mapping."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from span_panel_api import (
    SpanBatterySnapshot,
    SpanCircuitSnapshot,
    SpanEvseSnapshot,
    SpanPanelSnapshot,
    SpanPVSnapshot,
)

from homeassistant.components.span_panel.schema_expectations import (
    SENSOR_FIELD_MAP,
    all_referenced_field_paths,
)
from homeassistant.components.span_panel.schema_validation import (
    validate_field_metadata,
)
from homeassistant.components.span_panel.sensor_definitions import (
    BATTERY_POWER_SENSOR,
    BATTERY_SENSOR,
    BESS_METADATA_SENSORS,
    CIRCUIT_BREAKER_RATING_SENSOR,
    CIRCUIT_CURRENT_SENSOR,
    CIRCUIT_SENSORS,
    DOWNSTREAM_L1_CURRENT_SENSOR,
    DOWNSTREAM_L2_CURRENT_SENSOR,
    EVSE_SENSORS,
    GRID_POWER_FLOW_SENSOR,
    L1_VOLTAGE_SENSOR,
    L2_VOLTAGE_SENSOR,
    MAIN_BREAKER_RATING_SENSOR,
    PANEL_DATA_STATUS_SENSORS,
    PANEL_ENERGY_SENSORS,
    PANEL_POWER_SENSORS,
    PV_METADATA_SENSORS,
    PV_POWER_SENSOR,
    SITE_POWER_SENSOR,
    STATUS_SENSORS,
    UNMAPPED_SENSORS,
    UPSTREAM_L1_CURRENT_SENSOR,
    UPSTREAM_L2_CURRENT_SENSOR,
)

_LOGGER_NAME = "homeassistant.components.span_panel.schema_validation"


# ---------------------------------------------------------------------------
# Sensor field mapping tests
# ---------------------------------------------------------------------------


class TestSensorFieldMap:
    """Tests for the sensor-to-snapshot-field mapping."""

    def test_no_empty_keys_or_paths(self) -> None:
        """Every entry must have non-empty sensor key and field path."""
        for sensor_key, field_path in SENSOR_FIELD_MAP.items():
            assert sensor_key, "Empty sensor key in SENSOR_FIELD_MAP"
            assert field_path, f"Empty field path for sensor key '{sensor_key}'"

    def test_field_paths_follow_convention(self) -> None:
        """All field paths must be {snapshot_type}.{field_name}."""
        valid_prefixes = {"panel", "circuit", "battery", "pv", "evse"}
        for sensor_key, field_path in SENSOR_FIELD_MAP.items():
            parts = field_path.split(".", 1)
            assert len(parts) == 2, (
                f"Field path '{field_path}' for sensor '{sensor_key}' "
                f"does not follow 'type.field' convention"
            )
            assert parts[0] in valid_prefixes, (
                f"Field path '{field_path}' for sensor '{sensor_key}' "
                f"has unknown prefix '{parts[0]}'"
            )

    def test_sensor_keys_exist_in_definitions(self) -> None:
        """Every sensor key should match a real sensor definition."""
        all_defs = [
            *PANEL_DATA_STATUS_SENSORS,
            *STATUS_SENSORS,
            *UNMAPPED_SENSORS,
            BATTERY_SENSOR,
            L1_VOLTAGE_SENSOR,
            L2_VOLTAGE_SENSOR,
            UPSTREAM_L1_CURRENT_SENSOR,
            UPSTREAM_L2_CURRENT_SENSOR,
            DOWNSTREAM_L1_CURRENT_SENSOR,
            DOWNSTREAM_L2_CURRENT_SENSOR,
            MAIN_BREAKER_RATING_SENSOR,
            CIRCUIT_CURRENT_SENSOR,
            CIRCUIT_BREAKER_RATING_SENSOR,
            *BESS_METADATA_SENSORS,
            *PV_METADATA_SENSORS,
            *PANEL_POWER_SENSORS,
            BATTERY_POWER_SENSOR,
            PV_POWER_SENSOR,
            GRID_POWER_FLOW_SENSOR,
            SITE_POWER_SENSOR,
            *PANEL_ENERGY_SENSORS,
            *CIRCUIT_SENSORS,
            *EVSE_SENSORS,
        ]
        known_keys = {d.key for d in all_defs}

        for sensor_key in SENSOR_FIELD_MAP:
            assert sensor_key in known_keys, (
                f"Sensor key '{sensor_key}' in SENSOR_FIELD_MAP not found in sensor definitions"
            )

    def test_field_paths_match_snapshot_attrs(self) -> None:
        """Field names should match actual snapshot dataclass attributes."""
        snapshot_classes = {
            "panel": SpanPanelSnapshot,
            "circuit": SpanCircuitSnapshot,
            "battery": SpanBatterySnapshot,
            "pv": SpanPVSnapshot,
            "evse": SpanEvseSnapshot,
        }

        for sensor_key, field_path in SENSOR_FIELD_MAP.items():
            prefix, field_name = field_path.split(".", 1)
            cls = snapshot_classes[prefix]
            assert hasattr(cls, field_name) or field_name in {
                f.name for f in cls.__dataclass_fields__.values()
            }, (
                f"Field '{field_name}' from path '{field_path}' "
                f"(sensor '{sensor_key}') not found on {cls.__name__}"
            )

    def test_all_referenced_field_paths(self) -> None:
        """all_referenced_field_paths should return all unique values."""
        paths = all_referenced_field_paths()
        assert paths == frozenset(SENSOR_FIELD_MAP.values())


# ---------------------------------------------------------------------------
# Unit cross-check tests
# ---------------------------------------------------------------------------


def _make_sensor_def(key: str, unit: str | None) -> MagicMock:
    """Create a minimal mock SensorEntityDescription with key and unit."""
    mock = MagicMock(spec=["key", "native_unit_of_measurement"])
    mock.key = key
    mock.native_unit_of_measurement = unit
    return mock


class TestUnitCrossCheck:
    """Tests for field metadata unit vs sensor definition unit cross-checking."""

    def test_matching_units_no_cross_check_message(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Matching units should produce no cross-check log messages."""
        metadata = {"panel.instant_grid_power_w": {"unit": "W", "datatype": "float"}}
        sensor_defs = {"instantGridPowerW": _make_sensor_def("instantGridPowerW", "W")}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        assert not any("cross-check" in r.lower() for r in caplog.messages)

    def test_mismatched_units_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unit mismatch should produce a debug message naming both units."""
        metadata = {"panel.instant_grid_power_w": {"unit": "kW", "datatype": "float"}}
        sensor_defs = {"instantGridPowerW": _make_sensor_def("instantGridPowerW", "W")}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        cross_msgs = [m for m in caplog.messages if "cross-check" in m.lower()]
        assert len(cross_msgs) == 1
        assert "'kW'" in cross_msgs[0]
        assert "'W'" in cross_msgs[0]

    def test_missing_metadata_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sensor reading a field with no metadata should log debug."""
        metadata: dict[str, dict[str, object]] = {}
        sensor_defs = {"l1_voltage": _make_sensor_def("l1_voltage", "V")}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        assert any("no metadata" in m for m in caplog.messages)

    def test_missing_schema_unit_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Field with no unit in metadata but unit in sensor def should log debug."""
        metadata = {"panel.l1_voltage": {"datatype": "float"}}
        sensor_defs = {"l1_voltage": _make_sensor_def("l1_voltage", "V")}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        assert any("no unit" in m for m in caplog.messages)

    def test_sensor_without_unit_skipped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sensor with no native_unit_of_measurement should be skipped."""
        metadata = {"panel.main_relay_state": {"datatype": "enum"}}
        sensor_defs = {"main_relay_state": _make_sensor_def("main_relay_state", None)}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        assert not any("cross-check" in m.lower() for m in caplog.messages)

    def test_all_output_is_debug_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """All schema validation output should be DEBUG — never visible to users."""
        metadata = {
            "panel.instant_grid_power_w": {"unit": "kW", "datatype": "float"},
            "panel.l1_voltage": {"datatype": "float"},
            "panel.new_fancy_field": {"unit": "W", "datatype": "float"},
        }
        sensor_defs = {
            "instantGridPowerW": _make_sensor_def("instantGridPowerW", "W"),
            "l1_voltage": _make_sensor_def("l1_voltage", "V"),
        }
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata, sensor_defs=sensor_defs)
        above_debug = [r for r in caplog.records if r.levelno > logging.DEBUG]
        assert len(above_debug) == 0, (
            f"Expected all DEBUG, got: {[(r.levelname, r.getMessage()) for r in above_debug]}"
        )


# ---------------------------------------------------------------------------
# Unmapped field detection tests
# ---------------------------------------------------------------------------


class TestUnmappedFields:
    """Tests for detecting fields the integration doesn't consume."""

    def test_unmapped_field_logs_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """Field not in SENSOR_FIELD_MAP values should log at DEBUG."""
        metadata = {"panel.new_fancy_field": {"unit": "W", "datatype": "float"}}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata)
        assert any(
            r.levelno == logging.DEBUG and "new_fancy_field" in r.getMessage()
            for r in caplog.records
        )

    def test_mapped_field_not_reported(self, caplog: pytest.LogCaptureFixture) -> None:
        """Field that IS in SENSOR_FIELD_MAP should not be reported as unmapped."""
        metadata = {"panel.instant_grid_power_w": {"unit": "W", "datatype": "float"}}
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(metadata)
        assert not any("not mapped" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# No-op when metadata unavailable
# ---------------------------------------------------------------------------


class TestNoOp:
    """Tests for graceful handling when library doesn't expose metadata."""

    def test_none_metadata_is_noop(self, caplog: pytest.LogCaptureFixture) -> None:
        """None metadata should produce no output above DEBUG."""
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            validate_field_metadata(None)
        assert any("skipped" in m for m in caplog.messages)
        above_debug = [r for r in caplog.records if r.levelno > logging.DEBUG]
        assert len(above_debug) == 0
