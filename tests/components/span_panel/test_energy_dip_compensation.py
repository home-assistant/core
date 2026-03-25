"""Tests for energy dip compensation feature."""

# ruff: noqa: D102

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.span_panel.const import ENABLE_ENERGY_DIP_COMPENSATION
from homeassistant.components.span_panel.options import ENERGY_REPORTING_GRACE_PERIOD
from homeassistant.components.span_panel.sensor_base import (
    SpanEnergyExtraStoredData,
    SpanEnergySensorBase,
)


class DummyDipSensor(SpanEnergySensorBase):
    """Minimal concrete energy sensor for dip compensation tests."""

    def __init__(  # pylint: disable=super-init-not-called
        self,
        dip_enabled: bool = True,
        state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING,
    ) -> None:
        """Bypass parent __init__ to avoid full HA dependencies."""
        self.coordinator = SimpleNamespace(
            panel_offline=False,
            config_entry=SimpleNamespace(
                options={
                    ENERGY_REPORTING_GRACE_PERIOD: 15,
                    ENABLE_ENERGY_DIP_COMPENSATION: dip_enabled,
                },
            ),
            data=SimpleNamespace(),
            report_energy_dip=MagicMock(),
        )
        self._mock_panel_value: float | None = None
        self.entity_description = SimpleNamespace(
            device_class="energy",
            state_class=state_class,
            key="dummy",
            value_fn=lambda _: self._mock_panel_value,
            native_unit_of_measurement="Wh",
        )
        self._attr_native_value: float | None = None
        self._last_valid_state: float | None = None
        self._last_valid_changed = None
        self._grace_period_minutes = 15
        self._previous_circuit_name = None
        self._attr_unique_id = "dummy_sensor"
        self._attr_name = "Dummy"
        self._restored_from_storage: bool = False

        # Energy dip compensation state
        self._energy_offset: float = 0.0
        self._last_panel_reading: float | None = None
        self._last_dip_delta: float | None = None
        self._is_total_increasing: bool = (
            state_class == SensorStateClass.TOTAL_INCREASING
        )
        self._dip_compensation_enabled: bool = dip_enabled

    def _generate_unique_id(self, snapshot, description):
        return "dummy_sensor"

    def _generate_friendly_name(self, snapshot, description):
        return "Dummy"

    def get_data_source(self, snapshot):
        return "dummy_data"


# =============================================================================
# SpanEnergyExtraStoredData round-trip with new fields
# =============================================================================


class TestExtraStoredDataDipFields:
    """Tests for energy dip fields in SpanEnergyExtraStoredData."""

    def test_as_dict_includes_dip_fields(self):
        """Verify as_dict includes the three new dip fields."""
        data = SpanEnergyExtraStoredData(
            native_value=100.0,
            native_unit_of_measurement="Wh",
            last_valid_state=100.0,
            last_valid_changed="2025-12-01T00:00:00",
            energy_offset=5.0,
            last_panel_reading=95.0,
            last_dip_delta=5.0,
        )
        result = data.as_dict()
        assert result["energy_offset"] == 5.0
        assert result["last_panel_reading"] == 95.0
        assert result["last_dip_delta"] == 5.0

    def test_from_dict_restores_dip_fields(self):
        """Verify from_dict restores the three new dip fields."""
        stored = {
            "native_value": 200.0,
            "native_unit_of_measurement": "Wh",
            "last_valid_state": 200.0,
            "last_valid_changed": "2025-12-01T12:00:00",
            "energy_offset": 10.0,
            "last_panel_reading": 190.0,
            "last_dip_delta": 10.0,
        }
        result = SpanEnergyExtraStoredData.from_dict(stored)
        assert result is not None
        assert result.energy_offset == 10.0
        assert result.last_panel_reading == 190.0
        assert result.last_dip_delta == 10.0

    def test_backward_compat_missing_dip_fields(self):
        """Old stored data without dip fields deserializes with None."""
        stored = {
            "native_value": 300.0,
            "native_unit_of_measurement": "Wh",
            "last_valid_state": 300.0,
            "last_valid_changed": "2025-12-01T06:00:00",
        }
        result = SpanEnergyExtraStoredData.from_dict(stored)
        assert result is not None
        assert result.energy_offset is None
        assert result.last_panel_reading is None
        assert result.last_dip_delta is None

    def test_roundtrip_with_dip_fields(self):
        """Data survives a full round-trip through serialization."""
        original = SpanEnergyExtraStoredData(
            native_value=500.0,
            native_unit_of_measurement="Wh",
            last_valid_state=500.0,
            last_valid_changed="2025-12-01T09:00:00",
            energy_offset=25.0,
            last_panel_reading=475.0,
            last_dip_delta=8.0,
        )
        restored = SpanEnergyExtraStoredData.from_dict(original.as_dict())
        assert restored is not None
        assert restored.energy_offset == original.energy_offset
        assert restored.last_panel_reading == original.last_panel_reading
        assert restored.last_dip_delta == original.last_dip_delta

    def test_roundtrip_with_none_dip_fields(self):
        """None dip fields survive round-trip."""
        original = SpanEnergyExtraStoredData(
            native_value=100.0,
            native_unit_of_measurement="Wh",
            last_valid_state=100.0,
            last_valid_changed="2025-12-01T09:00:00",
            energy_offset=None,
            last_panel_reading=None,
            last_dip_delta=None,
        )
        restored = SpanEnergyExtraStoredData.from_dict(original.as_dict())
        assert restored is not None
        assert restored.energy_offset is None
        assert restored.last_panel_reading is None
        assert restored.last_dip_delta is None


# =============================================================================
# Dip compensation logic
# =============================================================================


class TestDipCompensation:
    """Tests for the core dip compensation logic in _process_raw_value."""

    def test_first_reading_sets_baseline(self):
        """First reading sets _last_panel_reading without applying offset."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        assert sensor._attr_native_value == 1000.0
        assert sensor._last_panel_reading == 1000.0
        assert sensor._energy_offset == 0.0

    def test_normal_increase_passthrough(self):
        """Normal increasing values pass through without offset."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 1100.0
        sensor._update_native_value()

        assert sensor._attr_native_value == 1100.0
        assert sensor._last_panel_reading == 1100.0
        assert sensor._energy_offset == 0.0

    def test_dip_applies_offset(self):
        """A dip in raw value produces compensated output."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Dip of 50 Wh
        sensor._mock_panel_value = 950.0
        sensor._update_native_value()

        # HA should see 950 + 50 = 1000
        assert sensor._attr_native_value == 1000.0
        assert sensor._energy_offset == 50.0
        assert sensor._last_panel_reading == 950.0
        assert sensor._last_dip_delta == 50.0

    def test_below_threshold_ignored(self):
        """Dips below 1.0 Wh threshold are not compensated."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Dip of 0.5 Wh — below threshold
        sensor._mock_panel_value = 999.5
        sensor._update_native_value()

        assert sensor._attr_native_value == 999.5
        assert sensor._energy_offset == 0.0
        assert sensor._last_dip_delta is None

    def test_multiple_dips_accumulate(self):
        """Multiple dips accumulate the offset."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # First dip: 20 Wh
        sensor._mock_panel_value = 980.0
        sensor._update_native_value()
        assert sensor._energy_offset == 20.0
        assert sensor._attr_native_value == 1000.0

        # Normal increase
        sensor._mock_panel_value = 1010.0
        sensor._update_native_value()
        assert sensor._attr_native_value == 1030.0  # 1010 + 20

        # Second dip: 30 Wh
        sensor._mock_panel_value = 980.0
        sensor._update_native_value()
        assert sensor._energy_offset == 50.0  # 20 + 30
        assert sensor._attr_native_value == 1030.0  # 980 + 50

    def test_disabled_passthrough(self):
        """When disabled, dips pass through without compensation."""
        sensor = DummyDipSensor(dip_enabled=False)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 950.0
        sensor._update_native_value()

        # No compensation — raw value passed through
        assert sensor._attr_native_value == 950.0
        assert sensor._energy_offset == 0.0

    def test_non_total_increasing_passthrough(self):
        """MEASUREMENT sensors pass through without compensation."""
        sensor = DummyDipSensor(
            dip_enabled=True,
            state_class=SensorStateClass.MEASUREMENT,
        )

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 950.0
        sensor._update_native_value()

        # Not a TOTAL_INCREASING sensor — no compensation
        assert sensor._attr_native_value == 950.0
        assert sensor._energy_offset == 0.0

    def test_dip_reports_to_coordinator(self):
        """Dip detection calls coordinator.report_energy_dip."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor.entity_id = "sensor.test_energy"

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 950.0
        sensor._update_native_value()

        sensor.coordinator.report_energy_dip.assert_called_once_with(
            "sensor.test_energy", 50.0, 50.0
        )

    def test_no_report_when_no_dip(self):
        """Normal increases don't trigger coordinator notification."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 1100.0
        sensor._update_native_value()

        sensor.coordinator.report_energy_dip.assert_not_called()

    def test_exactly_at_threshold_triggers(self):
        """A dip of exactly 1.0 Wh triggers compensation."""
        sensor = DummyDipSensor(dip_enabled=True)

        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        sensor._mock_panel_value = 999.0
        sensor._update_native_value()

        assert sensor._energy_offset == 1.0
        assert sensor._attr_native_value == 1000.0


# =============================================================================
# Extra state attributes
# =============================================================================


class TestDipAttributes:
    """Tests for energy dip compensation state attributes."""

    def test_shown_when_offset_nonzero(self):
        """Attributes include energy_offset when it is nonzero."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor._energy_offset = 25.0
        sensor._last_dip_delta = 10.0

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["energy_offset"] == "25.0"
        assert attrs["last_dip_delta"] == "10.0"

    def test_hidden_when_offset_zero_no_dip(self):
        """Attributes omit energy_offset when zero and no dip has occurred."""
        sensor = DummyDipSensor(dip_enabled=True)
        # Defaults: offset=0.0, last_dip_delta=None

        attrs = sensor.extra_state_attributes
        # No dip fields should appear
        assert attrs is None or "energy_offset" not in attrs

    def test_hidden_when_disabled(self):
        """Dip attributes are not shown when compensation is disabled."""
        sensor = DummyDipSensor(dip_enabled=False)
        sensor._energy_offset = 25.0
        sensor._last_dip_delta = 10.0

        attrs = sensor.extra_state_attributes
        assert attrs is None or "energy_offset" not in attrs

    def test_last_dip_shown_when_dip_occurred(self):
        """last_dip_delta appears even when offset is zero (shouldn't happen, but edge case)."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor._energy_offset = 0.0
        sensor._last_dip_delta = 5.0

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["last_dip_delta"] == "5.0"
        # energy_offset is 0, should not be included
        assert "energy_offset" not in attrs


# =============================================================================
# Restoration
# =============================================================================


class TestDipRestoration:
    """Tests for dip compensation state restoration."""

    def test_offset_restored_when_enabled(self):
        """Verify _energy_offset is restored from stored data when enabled."""
        sensor = DummyDipSensor(dip_enabled=True)

        # Simulate what async_added_to_hass restoration does
        restored = SpanEnergyExtraStoredData(
            native_value=1000.0,
            native_unit_of_measurement="Wh",
            last_valid_state=1000.0,
            last_valid_changed="2025-12-01T00:00:00",
            energy_offset=50.0,
            last_panel_reading=950.0,
            last_dip_delta=10.0,
        )

        # Apply restoration (mimicking the async_added_to_hass logic)
        if sensor._dip_compensation_enabled and sensor._is_total_increasing:
            if restored.energy_offset is not None:
                sensor._energy_offset = restored.energy_offset
            if restored.last_panel_reading is not None:
                sensor._last_panel_reading = restored.last_panel_reading
            if restored.last_dip_delta is not None:
                sensor._last_dip_delta = restored.last_dip_delta

        assert sensor._energy_offset == 50.0
        assert sensor._last_panel_reading == 950.0
        assert sensor._last_dip_delta == 10.0

    def test_offset_not_restored_when_disabled(self):
        """Verify offsets are NOT restored when compensation is disabled."""
        sensor = DummyDipSensor(dip_enabled=False)

        restored = SpanEnergyExtraStoredData(
            native_value=1000.0,
            native_unit_of_measurement="Wh",
            last_valid_state=1000.0,
            last_valid_changed="2025-12-01T00:00:00",
            energy_offset=50.0,
            last_panel_reading=950.0,
            last_dip_delta=10.0,
        )

        # Apply restoration logic (gate on enabled flag)
        if sensor._dip_compensation_enabled and sensor._is_total_increasing:
            if restored.energy_offset is not None:
                sensor._energy_offset = restored.energy_offset

        # Disabled — should remain at defaults
        assert sensor._energy_offset == 0.0
        assert sensor._last_panel_reading is None
        assert sensor._last_dip_delta is None

    def test_extra_restore_state_data_includes_dip_fields(self):
        """extra_restore_state_data includes the dip compensation fields."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor._attr_native_value = 1000.0
        sensor._energy_offset = 25.0
        sensor._last_panel_reading = 975.0
        sensor._last_dip_delta = 5.0
        sensor._last_valid_state = 1000.0

        stored = sensor.extra_restore_state_data
        d = stored.as_dict()
        assert d["energy_offset"] == 25.0
        assert d["last_panel_reading"] == 975.0
        assert d["last_dip_delta"] == 5.0

    def test_extra_restore_state_data_zero_offset_stored_as_none(self):
        """Zero offset is stored as None to keep stored data compact."""
        sensor = DummyDipSensor(dip_enabled=True)
        sensor._attr_native_value = 1000.0
        sensor._energy_offset = 0.0

        stored = sensor.extra_restore_state_data
        d = stored.as_dict()
        assert d["energy_offset"] is None
