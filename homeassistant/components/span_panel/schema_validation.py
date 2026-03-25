"""Schema validation — cross-check field metadata against sensor definitions.

Compares the ``span-panel-api`` library's field metadata (schema-derived units
and datatypes keyed by snapshot field paths) against the integration's sensor
definitions. All Homie/MQTT knowledge stays in the library; this module only
sees snapshot field paths and HA sensor metadata.

Schema drift detection (diffing schema versions between firmware updates) is
the library's responsibility. The integration only consumes the result.

All output is log-only. No entity creation or sensor behavior changes.

Phase 1 of the schema-driven changes plan.

Usage:
    Called from the coordinator after the first successful data refresh.
    Requires ``span-panel-api`` to expose field metadata via the client protocol.
    Until that library change lands, ``validate_field_metadata()`` is a safe no-op.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntityDescription

from .schema_expectations import SENSOR_FIELD_MAP, all_referenced_field_paths
from .sensor_definitions import (
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

_LOGGER = logging.getLogger(__name__)


def _cross_check_units(
    field_metadata: dict[str, dict[str, object]],
    sensor_defs: dict[str, SensorEntityDescription],
) -> None:
    """Compare library-reported units against sensor definition units.

    For each sensor in SENSOR_FIELD_MAP that has a ``native_unit_of_measurement``,
    look up the corresponding field path in the library's metadata and compare
    the declared unit.
    """
    for sensor_key, field_path in SENSOR_FIELD_MAP.items():
        sensor_def = sensor_defs.get(sensor_key)
        if sensor_def is None:
            continue

        ha_unit = sensor_def.native_unit_of_measurement
        if ha_unit is None:
            # Sensor has no unit (enum, string) — nothing to cross-check
            continue

        field_info = field_metadata.get(field_path)
        if field_info is None:
            _LOGGER.debug(
                "Schema cross-check: sensor '%s' reads field '%s' but "
                "library reports no metadata for it",
                sensor_key,
                field_path,
            )
            continue

        schema_unit = field_info.get("unit")
        if schema_unit is None:
            _LOGGER.debug(
                "Schema cross-check: field '%s' (sensor '%s') has no unit "
                "in library metadata, integration expects '%s'",
                field_path,
                sensor_key,
                ha_unit,
            )
        elif str(schema_unit) != str(ha_unit):
            _LOGGER.debug(
                "Schema cross-check: field '%s' (sensor '%s') unit is '%s' "
                "in library metadata, integration expects '%s'",
                field_path,
                sensor_key,
                schema_unit,
                ha_unit,
            )


def _report_unmapped_fields(
    field_metadata: dict[str, dict[str, object]],
) -> None:
    """Log fields in library metadata that no sensor definition references."""
    referenced = all_referenced_field_paths()
    for field_path in sorted(set(field_metadata) - referenced):
        _LOGGER.debug(
            "Schema: field '%s' in library metadata is not mapped to any sensor",
            field_path,
        )


def validate_field_metadata(
    field_metadata: dict[str, dict[str, object]] | None,
    sensor_defs: dict[str, SensorEntityDescription] | None = None,
) -> None:
    """Run integration-side schema validation checks.

    Args:
        field_metadata: The library's field metadata, keyed by snapshot field
            path (e.g. ``"panel.instant_grid_power_w"``). Each value is a dict
            with at least ``"unit"`` and ``"datatype"`` keys. None if the
            library does not yet expose metadata.
        sensor_defs: Dict of sensor_key → SensorEntityDescription for unit
            cross-checking. None skips the cross-check.

    """
    if field_metadata is None:
        _LOGGER.debug(
            "Schema validation skipped — library does not expose field metadata"
        )
        return

    if sensor_defs is not None:
        _cross_check_units(field_metadata, sensor_defs)

    _report_unmapped_fields(field_metadata)


def collect_sensor_definitions() -> dict[str, SensorEntityDescription]:
    """Collect all sensor definitions into a dict keyed by sensor key.

    Only includes sensors that appear in SENSOR_FIELD_MAP (i.e. sensors
    that read a single snapshot field and are eligible for cross-checking).
    """
    all_defs: list[SensorEntityDescription] = [
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
    mapped_keys = set(SENSOR_FIELD_MAP.keys())
    return {d.key: d for d in all_defs if d.key in mapped_keys}
