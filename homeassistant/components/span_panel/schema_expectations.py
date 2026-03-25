"""Sensor-to-snapshot-field mapping for schema validation.

Maps integration sensor definition keys to snapshot field paths. This is the
integration's declaration of which snapshot fields it reads, expressed in
transport-agnostic terms.

The integration does NOT know about Homie, MQTT, node types, or property IDs.
The ``span-panel-api`` library owns that knowledge and exposes field-level
metadata keyed by snapshot field paths. This module bridges from sensor
definitions (HA side) to field paths (library side).

Field path convention: ``{snapshot_type}.{field_name}``
  - ``panel`` — SpanPanelSnapshot fields
  - ``circuit`` — SpanCircuitSnapshot fields
  - ``battery`` — SpanBatterySnapshot fields
  - ``pv`` — SpanPVSnapshot fields
  - ``evse`` — SpanEvseSnapshot fields

Derived sensors (net energy, dsm_state, current_run_config) that compute
values from multiple fields have no single source field and are excluded.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Sensor definition key → snapshot field path
#
# Every sensor the integration creates that reads a single snapshot field
# should appear here. The sensor definition provides the HA unit; the
# library's field metadata provides the schema-declared unit. The validation
# module compares them.
#
# Entries are grouped by snapshot type for readability.
# ---------------------------------------------------------------------------

SENSOR_FIELD_MAP: dict[str, str] = {
    # --- Panel power sensors -------------------------------------------------
    "instantGridPowerW": "panel.instant_grid_power_w",
    "feedthroughPowerW": "panel.feedthrough_power_w",
    "batteryPowerW": "panel.power_flow_battery",
    "pvPowerW": "panel.power_flow_pv",
    "gridPowerFlowW": "panel.power_flow_grid",
    "sitePowerW": "panel.power_flow_site",
    # --- Panel energy sensors ------------------------------------------------
    "mainMeterEnergyProducedWh": "panel.main_meter_energy_produced_wh",
    "mainMeterEnergyConsumedWh": "panel.main_meter_energy_consumed_wh",
    "feedthroughEnergyProducedWh": "panel.feedthrough_energy_produced_wh",
    "feedthroughEnergyConsumedWh": "panel.feedthrough_energy_consumed_wh",
    # --- Panel diagnostic sensors --------------------------------------------
    "l1_voltage": "panel.l1_voltage",
    "l2_voltage": "panel.l2_voltage",
    "upstream_l1_current": "panel.upstream_l1_current_a",
    "upstream_l2_current": "panel.upstream_l2_current_a",
    "downstream_l1_current": "panel.downstream_l1_current_a",
    "downstream_l2_current": "panel.downstream_l2_current_a",
    "main_breaker_rating": "panel.main_breaker_rating_a",
    # --- Panel status sensors (enum/string — no unit, but tracked) -----------
    "main_relay_state": "panel.main_relay_state",
    "grid_forming_entity": "panel.dominant_power_source",
    "vendor_cloud": "panel.vendor_cloud",
    "software_version": "panel.firmware_version",
    # --- Circuit sensors -----------------------------------------------------
    "circuit_power": "circuit.instant_power_w",
    "circuit_energy_produced": "circuit.produced_energy_wh",
    "circuit_energy_consumed": "circuit.consumed_energy_wh",
    "circuit_current": "circuit.current_a",
    "circuit_breaker_rating": "circuit.breaker_rating_a",
    # --- Unmapped circuit sensors (same fields, different sensor keys) --------
    "instantPowerW": "circuit.instant_power_w",
    "producedEnergyWh": "circuit.produced_energy_wh",
    "consumedEnergyWh": "circuit.consumed_energy_wh",
    # --- Battery sensors -----------------------------------------------------
    "storage_battery_percentage": "battery.soe_percentage",
    "nameplate_capacity": "battery.nameplate_capacity_kwh",
    "soe_kwh": "battery.soe_kwh",
    # --- BESS metadata sensors -----------------------------------------------
    "vendor": "battery.vendor_name",
    "model": "battery.product_name",
    "serial_number": "battery.serial_number",
    "firmware_version": "battery.software_version",
    # --- PV metadata sensors -------------------------------------------------
    "pv_vendor": "pv.vendor_name",
    "pv_product": "pv.product_name",
    "pv_nameplate_capacity": "pv.nameplate_capacity_w",
    # --- EVSE sensors --------------------------------------------------------
    "evse_status": "evse.status",
    "evse_advertised_current": "evse.advertised_current_a",
    "evse_lock_state": "evse.lock_state",
}

# Derived sensors excluded from the map (computed from multiple fields):
#   dsm_state          — multi-signal heuristic
#   dsm_grid_state     — deprecated alias for dsm_state
#   current_run_config — tri-state derivation
#   mainMeterNetEnergyWh     — consumed_wh - produced_wh
#   feedthroughNetEnergyWh   — consumed_wh - produced_wh
#   circuit_energy_net       — consumed_wh - produced_wh (or inverse for PV)


def all_referenced_field_paths() -> frozenset[str]:
    """Return the set of all snapshot field paths referenced by any sensor."""
    return frozenset(SENSOR_FIELD_MAP.values())
