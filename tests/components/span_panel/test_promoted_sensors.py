"""Tests for promoted sensor entities (Phase 1-4 of sensor promotion plan).

Covers:
- Panel diagnostic sensors (voltage, lug currents, breaker rating)
- Grid islandable binary sensor
- BESS metadata sensors and sub-device info
- PV metadata sensors
- EVSE sensor value functions
- Conditional sensor creation gating
- BESS unique ID helpers
"""

# ruff: noqa: D102

from span_panel_api import SpanPVSnapshot

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.span_panel.binary_sensor import GRID_ISLANDABLE_SENSOR
from homeassistant.components.span_panel.const import DOMAIN
from homeassistant.components.span_panel.helpers import (
    build_bess_unique_id,
    has_bess,
    has_evse,
    has_pv,
)
from homeassistant.components.span_panel.sensor_definitions import (
    BESS_METADATA_SENSORS,
    CIRCUIT_BREAKER_RATING_SENSOR,
    CIRCUIT_CURRENT_SENSOR,
    DOWNSTREAM_L1_CURRENT_SENSOR,
    DOWNSTREAM_L2_CURRENT_SENSOR,
    EVSE_SENSORS,
    L1_VOLTAGE_SENSOR,
    L2_VOLTAGE_SENSOR,
    MAIN_BREAKER_RATING_SENSOR,
    PV_METADATA_SENSORS,
    UPSTREAM_L1_CURRENT_SENSOR,
    UPSTREAM_L2_CURRENT_SENSOR,
)
from homeassistant.components.span_panel.util import bess_device_info
from homeassistant.helpers.entity import EntityCategory

from .factories import (
    SpanBatterySnapshotFactory,
    SpanEvseSnapshotFactory,
    SpanPanelSnapshotFactory,
)

PANEL_DIAGNOSTIC_SENSORS = (
    L1_VOLTAGE_SENSOR,
    L2_VOLTAGE_SENSOR,
    UPSTREAM_L1_CURRENT_SENSOR,
    UPSTREAM_L2_CURRENT_SENSOR,
    DOWNSTREAM_L1_CURRENT_SENSOR,
    DOWNSTREAM_L2_CURRENT_SENSOR,
    MAIN_BREAKER_RATING_SENSOR,
)

# ---------------------------------------------------------------------------
# Phase 1: Panel diagnostic sensors
# ---------------------------------------------------------------------------


class TestPanelDiagnosticSensorDefinitions:
    """Test panel diagnostic sensor definitions (voltage, currents, breaker)."""

    def test_l1_voltage_definition(self):
        desc = next(d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "l1_voltage")
        assert desc.translation_key == "l1_voltage"
        assert desc.device_class == SensorDeviceClass.VOLTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_l2_voltage_definition(self):
        desc = next(d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "l2_voltage")
        assert desc.translation_key == "l2_voltage"
        assert desc.device_class == SensorDeviceClass.VOLTAGE

    def test_upstream_l1_current_definition(self):
        desc = next(
            d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "upstream_l1_current"
        )
        assert desc.translation_key == "upstream_l1_current"
        assert desc.device_class == SensorDeviceClass.CURRENT
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_downstream_l2_current_definition(self):
        desc = next(
            d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "downstream_l2_current"
        )
        assert desc.device_class == SensorDeviceClass.CURRENT

    def test_main_breaker_rating_definition(self):
        desc = next(
            d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "main_breaker_rating"
        )
        assert desc.translation_key == "main_breaker_rating"
        assert desc.device_class == SensorDeviceClass.CURRENT
        assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_voltage_value_functions(self):
        snapshot = SpanPanelSnapshotFactory.create(l1_voltage=121.5, l2_voltage=119.3)
        l1 = next(d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "l1_voltage")
        l2 = next(d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "l2_voltage")
        assert l1.value_fn(snapshot) == 121.5
        assert l2.value_fn(snapshot) == 119.3

    def test_lug_current_value_functions(self):
        snapshot = SpanPanelSnapshotFactory.create()
        # Default snapshot has None for these fields
        for key in (
            "upstream_l1_current",
            "upstream_l2_current",
            "downstream_l1_current",
            "downstream_l2_current",
        ):
            desc = next(d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == key)
            assert desc.value_fn(snapshot) is None

    def test_main_breaker_rating_value_function(self):
        snapshot = SpanPanelSnapshotFactory.create(main_breaker_rating_a=200)
        desc = next(
            d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "main_breaker_rating"
        )
        assert desc.value_fn(snapshot) == 200

    def test_main_breaker_rating_none(self):
        snapshot = SpanPanelSnapshotFactory.create(main_breaker_rating_a=None)
        desc = next(
            d for d in PANEL_DIAGNOSTIC_SENSORS if d.key == "main_breaker_rating"
        )
        assert desc.value_fn(snapshot) is None

    def test_all_diagnostic_sensors_have_translation_keys(self):
        for desc in PANEL_DIAGNOSTIC_SENSORS:
            assert desc.translation_key is not None, (
                f"Sensor {desc.key} missing translation_key"
            )


# ---------------------------------------------------------------------------
# Phase 1.4: Grid islandable binary sensor
# ---------------------------------------------------------------------------


class TestGridIslandableBinarySensor:
    """Test grid_islandable binary sensor definition."""

    def test_definition_exists(self):
        assert GRID_ISLANDABLE_SENSOR.key == "grid_islandable"
        assert GRID_ISLANDABLE_SENSOR.translation_key == "grid_islandable"
        assert GRID_ISLANDABLE_SENSOR.entity_category == EntityCategory.DIAGNOSTIC

    def test_value_function_true(self):
        snapshot = SpanPanelSnapshotFactory.create(grid_islandable=True)
        assert GRID_ISLANDABLE_SENSOR.value_fn(snapshot) is True

    def test_value_function_false(self):
        snapshot = SpanPanelSnapshotFactory.create(grid_islandable=False)
        assert GRID_ISLANDABLE_SENSOR.value_fn(snapshot) is False

    def test_value_function_none(self):
        snapshot = SpanPanelSnapshotFactory.create(grid_islandable=None)
        assert GRID_ISLANDABLE_SENSOR.value_fn(snapshot) is None


# ---------------------------------------------------------------------------
# Phase 2: Circuit current and breaker rating sensors
# ---------------------------------------------------------------------------


class TestCircuitSensorDefinitions:
    """Test circuit-level promoted sensor definitions."""

    def test_circuit_current_definition(self):
        assert CIRCUIT_CURRENT_SENSOR.key == "circuit_current"
        assert CIRCUIT_CURRENT_SENSOR.device_class == SensorDeviceClass.CURRENT
        assert CIRCUIT_CURRENT_SENSOR.state_class == SensorStateClass.MEASUREMENT
        assert CIRCUIT_CURRENT_SENSOR.name == "Current"

    def test_circuit_breaker_rating_definition(self):
        assert CIRCUIT_BREAKER_RATING_SENSOR.key == "circuit_breaker_rating"
        assert CIRCUIT_BREAKER_RATING_SENSOR.device_class == SensorDeviceClass.CURRENT
        assert (
            CIRCUIT_BREAKER_RATING_SENSOR.entity_category == EntityCategory.DIAGNOSTIC
        )
        assert CIRCUIT_BREAKER_RATING_SENSOR.name == "Breaker Rating"


# ---------------------------------------------------------------------------
# Phase 3: BESS sub-device and metadata sensors
# ---------------------------------------------------------------------------


class TestBessDeviceInfo:
    """Test BESS device info construction."""

    def test_bess_device_info_basic(self):
        battery = SpanBatterySnapshotFactory.create(
            vendor_name="Tesla",
            product_name="Powerwall 2",
            serial_number="TW-001",
            software_version="2.1.0",
        )
        info = bess_device_info("sp3-242424-001", battery, "My Panel")
        assert info.get("identifiers") == {(DOMAIN, "sp3-242424-001_bess")}
        assert info.get("name") == "My Panel Battery"
        assert info.get("manufacturer") == "Tesla"
        assert info.get("model") == "Powerwall 2"
        assert info.get("serial_number") == "TW-001"
        assert info.get("sw_version") == "2.1.0"
        assert info.get("via_device") == (DOMAIN, "sp3-242424-001")

    def test_bess_device_info_defaults_when_none(self):
        battery = SpanBatterySnapshotFactory.create()
        info = bess_device_info("serial", battery, "Panel")
        assert info.get("manufacturer") == "Unknown"
        assert info.get("model") == "Battery Storage"
        assert info.get("serial_number") is None
        assert info.get("sw_version") is None


class TestBessMetadataSensorDefinitions:
    """Test BESS metadata sensor definitions."""

    def test_sensor_count(self):
        assert len(BESS_METADATA_SENSORS) == 6

    def test_all_have_translation_keys(self):
        for desc in BESS_METADATA_SENSORS:
            assert desc.translation_key is not None, (
                f"BESS sensor {desc.key} missing translation_key"
            )

    def test_all_are_diagnostic(self):
        for desc in BESS_METADATA_SENSORS:
            assert desc.entity_category == EntityCategory.DIAGNOSTIC, (
                f"BESS sensor {desc.key} not diagnostic"
            )

    def test_vendor_value_function(self):
        battery = SpanBatterySnapshotFactory.create(vendor_name="Enphase")
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "vendor")
        assert desc.value_fn(battery) == "Enphase"

    def test_model_value_function(self):
        battery = SpanBatterySnapshotFactory.create(product_name="IQ Battery 10")
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "model")
        assert desc.value_fn(battery) == "IQ Battery 10"

    def test_serial_number_value_function(self):
        battery = SpanBatterySnapshotFactory.create(serial_number="BESS-12345")
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "serial_number")
        assert desc.value_fn(battery) == "BESS-12345"

    def test_firmware_version_value_function(self):
        battery = SpanBatterySnapshotFactory.create(software_version="3.0.1")
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "firmware_version")
        assert desc.value_fn(battery) == "3.0.1"

    def test_nameplate_capacity_value_function(self):
        battery = SpanBatterySnapshotFactory.create(nameplate_capacity_kwh=13.5)
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "nameplate_capacity")
        assert desc.value_fn(battery) == 13.5
        assert desc.device_class == SensorDeviceClass.ENERGY_STORAGE

    def test_soe_kwh_value_function(self):
        battery = SpanBatterySnapshotFactory.create(soe_kwh=10.2)
        desc = next(d for d in BESS_METADATA_SENSORS if d.key == "soe_kwh")
        assert desc.value_fn(battery) == 10.2
        assert desc.device_class == SensorDeviceClass.ENERGY_STORAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_none_metadata_returns_none(self):
        battery = SpanBatterySnapshotFactory.create()
        for desc in BESS_METADATA_SENSORS:
            if desc.key in ("vendor", "model", "serial_number", "firmware_version"):
                assert desc.value_fn(battery) is None, f"{desc.key} should be None"


class TestBessUniqueId:
    """Test BESS unique ID helper."""

    def test_build_bess_unique_id(self):
        result = build_bess_unique_id("sp3-serial-001", "vendor")
        assert result == "span_sp3-serial-001_bess_vendor"

    def test_build_bess_unique_id_different_keys(self):
        for key in (
            "vendor",
            "model",
            "serial_number",
            "firmware_version",
            "nameplate_capacity",
            "soe_kwh",
        ):
            result = build_bess_unique_id("serial", key)
            assert result == f"span_serial_bess_{key}"


# ---------------------------------------------------------------------------
# Phase 4: PV metadata sensors
# ---------------------------------------------------------------------------


class TestPVMetadataSensorDefinitions:
    """Test PV metadata sensor definitions."""

    def test_sensor_count(self):
        assert len(PV_METADATA_SENSORS) == 3

    def test_all_have_translation_keys(self):
        for desc in PV_METADATA_SENSORS:
            assert desc.translation_key is not None, (
                f"PV sensor {desc.key} missing translation_key"
            )

    def test_all_are_diagnostic(self):
        for desc in PV_METADATA_SENSORS:
            assert desc.entity_category == EntityCategory.DIAGNOSTIC, (
                f"PV sensor {desc.key} not diagnostic"
            )

    def test_pv_vendor_value_function(self):
        snapshot = SpanPanelSnapshotFactory.create(
            pv=SpanPVSnapshot(vendor_name="SolarEdge")
        )
        desc = next(d for d in PV_METADATA_SENSORS if d.key == "pv_vendor")
        assert desc.value_fn(snapshot) == "SolarEdge"

    def test_pv_product_value_function(self):
        snapshot = SpanPanelSnapshotFactory.create(
            pv=SpanPVSnapshot(product_name="SE7600H")
        )
        desc = next(d for d in PV_METADATA_SENSORS if d.key == "pv_product")
        assert desc.value_fn(snapshot) == "SE7600H"

    def test_pv_nameplate_capacity_value_function(self):
        snapshot = SpanPanelSnapshotFactory.create(
            pv=SpanPVSnapshot(nameplate_capacity_w=7600.0)
        )
        desc = next(d for d in PV_METADATA_SENSORS if d.key == "pv_nameplate_capacity")
        assert desc.value_fn(snapshot) == 7600.0
        assert desc.device_class == SensorDeviceClass.POWER

    def test_pv_none_metadata(self):
        snapshot = SpanPanelSnapshotFactory.create(pv=SpanPVSnapshot())
        for desc in PV_METADATA_SENSORS:
            assert desc.value_fn(snapshot) is None, f"PV {desc.key} should be None"


# ---------------------------------------------------------------------------
# EVSE sensor value functions
# ---------------------------------------------------------------------------


class TestEvseSensorDefinitions:
    """Test EVSE sensor definitions."""

    def test_sensor_count(self):
        assert len(EVSE_SENSORS) == 3

    def test_all_have_translation_keys(self):
        for desc in EVSE_SENSORS:
            assert desc.translation_key is not None, (
                f"EVSE sensor {desc.key} missing translation_key"
            )

    def test_evse_status_value_function(self):
        evse = SpanEvseSnapshotFactory.create(status="CHARGING")
        desc = next(d for d in EVSE_SENSORS if d.key == "evse_status")
        assert desc.value_fn(evse) == "CHARGING"

    def test_evse_status_empty_falls_back(self):
        evse = SpanEvseSnapshotFactory.create(status="")
        desc = next(d for d in EVSE_SENSORS if d.key == "evse_status")
        assert desc.value_fn(evse) == "unknown"

    def test_evse_advertised_current(self):
        evse = SpanEvseSnapshotFactory.create(advertised_current_a=32.0)
        desc = next(d for d in EVSE_SENSORS if d.key == "evse_advertised_current")
        assert desc.value_fn(evse) == 32.0

    def test_evse_lock_state(self):
        evse = SpanEvseSnapshotFactory.create(lock_state="LOCKED")
        desc = next(d for d in EVSE_SENSORS if d.key == "evse_lock_state")
        assert desc.value_fn(evse) == "LOCKED"

    def test_evse_lock_state_empty_falls_back(self):
        evse = SpanEvseSnapshotFactory.create(lock_state="")
        desc = next(d for d in EVSE_SENSORS if d.key == "evse_lock_state")
        assert desc.value_fn(evse) == "unknown"


# ---------------------------------------------------------------------------
# Conditional creation gating
# ---------------------------------------------------------------------------


class TestConditionalSensorCreation:
    """Test that conditional sensors are gated on snapshot data."""

    def test_has_bess_true(self):
        battery = SpanBatterySnapshotFactory.create(soe_percentage=50.0)
        snapshot = SpanPanelSnapshotFactory.create(battery=battery)
        assert has_bess(snapshot) is True

    def test_has_bess_false_no_soe(self):
        battery = SpanBatterySnapshotFactory.create(soe_percentage=None)
        snapshot = SpanPanelSnapshotFactory.create(battery=battery)
        assert has_bess(snapshot) is False

    def test_has_pv_true(self):
        snapshot = SpanPanelSnapshotFactory.create(power_flow_pv=-3500.0)
        assert has_pv(snapshot) is True

    def test_has_pv_false(self):
        snapshot = SpanPanelSnapshotFactory.create(power_flow_pv=None)
        assert has_pv(snapshot) is False

    def test_has_evse_true(self):
        evse = {"evse-0": SpanEvseSnapshotFactory.create()}
        snapshot = SpanPanelSnapshotFactory.create(evse=evse)
        assert has_evse(snapshot) is True

    def test_has_evse_false(self):
        snapshot = SpanPanelSnapshotFactory.create(evse={})
        assert has_evse(snapshot) is False

    def test_diagnostic_sensors_none_gated(self):
        snapshot = SpanPanelSnapshotFactory.create(
            l1_voltage=None, l2_voltage=None, main_breaker_rating_a=None
        )
        for desc in PANEL_DIAGNOSTIC_SENSORS:
            if desc.key in ("l1_voltage", "l2_voltage", "main_breaker_rating"):
                assert desc.value_fn(snapshot) is None
