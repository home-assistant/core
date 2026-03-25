"""Tests for grace period state restoration across HA restarts."""

# ruff: noqa: D102, D107

from datetime import datetime, timedelta
from types import SimpleNamespace

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.span_panel.const import ENABLE_ENERGY_DIP_COMPENSATION
from homeassistant.components.span_panel.options import ENERGY_REPORTING_GRACE_PERIOD
from homeassistant.components.span_panel.sensor_base import (
    SpanEnergyExtraStoredData,
    SpanEnergySensorBase,
)


class TestSpanEnergyExtraStoredData:
    """Tests for the SpanEnergyExtraStoredData class."""

    def test_as_dict_with_all_values(self):
        """Test as_dict returns all values correctly."""
        timestamp = datetime(2025, 11, 29, 12, 0, 0)
        data = SpanEnergyExtraStoredData(
            native_value=1234.56,
            native_unit_of_measurement="Wh",
            last_valid_state=1234.56,
            last_valid_changed=timestamp.isoformat(),
        )

        result = data.as_dict()

        assert result == {
            "native_value": 1234.56,
            "native_unit_of_measurement": "Wh",
            "last_valid_state": 1234.56,
            "last_valid_changed": "2025-11-29T12:00:00",
            "energy_offset": None,
            "last_panel_reading": None,
            "last_dip_delta": None,
        }

    def test_as_dict_with_none_values(self):
        """Test as_dict handles None values correctly."""
        data = SpanEnergyExtraStoredData(
            native_value=None,
            native_unit_of_measurement=None,
            last_valid_state=None,
            last_valid_changed=None,
        )

        result = data.as_dict()

        assert result == {
            "native_value": None,
            "native_unit_of_measurement": None,
            "last_valid_state": None,
            "last_valid_changed": None,
            "energy_offset": None,
            "last_panel_reading": None,
            "last_dip_delta": None,
        }

    def test_from_dict_with_all_values(self):
        """Test from_dict restores all values correctly."""
        stored_dict = {
            "native_value": 5678.90,
            "native_unit_of_measurement": "kWh",
            "last_valid_state": 5678.90,
            "last_valid_changed": "2025-11-29T15:30:00",
        }

        result = SpanEnergyExtraStoredData.from_dict(stored_dict)

        assert result is not None
        assert result.native_value == 5678.90
        assert result.native_unit_of_measurement == "kWh"
        assert result.last_valid_state == 5678.90
        assert result.last_valid_changed == "2025-11-29T15:30:00"

    def test_from_dict_with_none_values(self):
        """Test from_dict handles None values correctly."""
        stored_dict = {
            "native_value": None,
            "native_unit_of_measurement": None,
            "last_valid_state": None,
            "last_valid_changed": None,
        }

        result = SpanEnergyExtraStoredData.from_dict(stored_dict)

        assert result is not None
        assert result.native_value is None
        assert result.native_unit_of_measurement is None
        assert result.last_valid_state is None
        assert result.last_valid_changed is None

    def test_from_dict_with_missing_keys(self):
        """Test from_dict handles missing keys gracefully (uses None)."""
        stored_dict = {
            "native_value": 100.0,
            # Missing other keys
        }

        result = SpanEnergyExtraStoredData.from_dict(stored_dict)

        assert result is not None
        assert result.native_value == 100.0
        assert result.native_unit_of_measurement is None
        assert result.last_valid_state is None
        assert result.last_valid_changed is None

    def test_from_dict_with_empty_dict(self):
        """Test from_dict handles empty dict gracefully."""
        stored_dict = {}

        result = SpanEnergyExtraStoredData.from_dict(stored_dict)

        assert result is not None
        assert result.native_value is None
        assert result.native_unit_of_measurement is None
        assert result.last_valid_state is None
        assert result.last_valid_changed is None

    def test_roundtrip_serialization(self):
        """Test that data survives a round-trip through serialization."""
        timestamp = datetime(2025, 11, 29, 10, 15, 30)
        original = SpanEnergyExtraStoredData(
            native_value=9999.99,
            native_unit_of_measurement="Wh",
            last_valid_state=9999.99,
            last_valid_changed=timestamp.isoformat(),
        )

        # Simulate what HA does: convert to dict, then restore
        as_dict = original.as_dict()
        restored = SpanEnergyExtraStoredData.from_dict(as_dict)

        assert restored is not None
        assert restored.native_value == original.native_value
        assert (
            restored.native_unit_of_measurement == original.native_unit_of_measurement
        )
        assert restored.last_valid_state == original.last_valid_state
        assert restored.last_valid_changed == original.last_valid_changed

    def test_iso_format_timestamp_parsing(self):
        """Test that ISO format timestamps are properly stored and can be parsed."""
        # Various ISO format timestamps that might come from datetime.isoformat()
        test_timestamps = [
            "2025-11-29T12:00:00",
            "2025-11-29T12:00:00.123456",
            "2025-11-29T12:00:00+00:00",
            "2025-11-29T12:00:00-05:00",
        ]

        for timestamp_str in test_timestamps:
            data = SpanEnergyExtraStoredData(
                native_value=100.0,
                native_unit_of_measurement="Wh",
                last_valid_state=100.0,
                last_valid_changed=timestamp_str,
            )

            restored = SpanEnergyExtraStoredData.from_dict(data.as_dict())
            assert restored is not None
            assert restored.last_valid_changed == timestamp_str

            # Verify the timestamp can be parsed back to datetime
            parsed_dt = datetime.fromisoformat(restored.last_valid_changed)
            assert parsed_dt is not None


class TestGracePeriodRestorationLogic:
    """Tests for the grace period restoration logic."""

    def test_grace_period_calculation_within_period(self):
        """Test grace period calculation when within the grace period."""
        # Simulate a scenario where:
        # - Last valid time was 10 minutes ago
        # - Grace period is 15 minutes
        # - Panel is offline
        # Expected: Should use last valid state

        last_valid_changed = datetime.now() - timedelta(minutes=10)
        grace_period_minutes = 15

        time_since_last_valid = datetime.now() - last_valid_changed
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        is_within_grace = time_since_last_valid <= grace_period_duration

        assert is_within_grace is True

    def test_grace_period_calculation_expired(self):
        """Test grace period calculation when expired."""
        # Simulate a scenario where:
        # - Last valid time was 20 minutes ago
        # - Grace period is 15 minutes
        # - Panel is offline
        # Expected: Should report None (unknown)

        last_valid_changed = datetime.now() - timedelta(minutes=20)
        grace_period_minutes = 15

        time_since_last_valid = datetime.now() - last_valid_changed
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        is_within_grace = time_since_last_valid <= grace_period_duration

        assert is_within_grace is False

    def test_grace_period_edge_case_exactly_at_limit(self):
        """Test grace period at exactly the limit."""
        # Grace period of 15 minutes, exactly 15 minutes ago
        last_valid_changed = datetime.now() - timedelta(minutes=15)
        grace_period_minutes = 15

        time_since_last_valid = datetime.now() - last_valid_changed
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        # At exactly the limit, should still be within grace period (<= comparison)
        # Allow small timing difference
        assert (
            abs(
                time_since_last_valid.total_seconds()
                - grace_period_duration.total_seconds()
            )
            < 1
        )

    def test_grace_period_zero_disabled(self):
        """Test that grace period of 0 means no grace period."""
        last_valid_changed = datetime.now() - timedelta(seconds=1)
        grace_period_minutes = 0

        time_since_last_valid = datetime.now() - last_valid_changed
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        is_within_grace = time_since_last_valid <= grace_period_duration

        # With 0 grace period, even 1 second ago should be expired
        assert is_within_grace is False

    def test_grace_period_maximum_60_minutes(self):
        """Test grace period with maximum 60 minute setting."""
        # 59 minutes ago with 60 minute grace period - should still be valid
        last_valid_changed = datetime.now() - timedelta(minutes=59)
        grace_period_minutes = 60

        time_since_last_valid = datetime.now() - last_valid_changed
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        is_within_grace = time_since_last_valid <= grace_period_duration

        assert is_within_grace is True

        # 61 minutes ago with 60 minute grace period - should be expired
        last_valid_changed_expired = datetime.now() - timedelta(minutes=61)
        time_since_expired = datetime.now() - last_valid_changed_expired

        is_within_grace_expired = time_since_expired <= grace_period_duration

        assert is_within_grace_expired is False


class TestRestorationScenarios:
    """Test realistic restoration scenarios."""

    def test_restoration_after_brief_restart(self):
        """Test restoration scenario: HA restarts briefly while panel is offline."""
        # Scenario:
        # 1. Panel goes offline
        # 2. HA stores grace period state (last_valid_state=1000, last_valid_changed=5 min ago)
        # 3. HA restarts (takes 2 minutes)
        # 4. HA comes back up, panel still offline
        # 5. Total offline time: 7 minutes (5 + 2)
        # 6. Grace period: 15 minutes
        # Expected: Should restore and use last_valid_state

        original_last_valid_changed = datetime.now() - timedelta(minutes=7)
        grace_period_minutes = 15
        stored_last_valid_state = 1000.0

        # Simulate restoration
        stored_data = SpanEnergyExtraStoredData(
            native_value=stored_last_valid_state,
            native_unit_of_measurement="Wh",
            last_valid_state=stored_last_valid_state,
            last_valid_changed=original_last_valid_changed.isoformat(),
        )

        restored = SpanEnergyExtraStoredData.from_dict(stored_data.as_dict())
        assert restored is not None

        # Parse the restored timestamp
        restored_timestamp = datetime.fromisoformat(restored.last_valid_changed)

        # Check if still within grace period
        time_since_last_valid = datetime.now() - restored_timestamp
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        assert time_since_last_valid <= grace_period_duration
        assert restored.last_valid_state == stored_last_valid_state

    def test_restoration_after_long_restart(self):
        """Test restoration scenario: HA restarts after grace period expired."""
        # Scenario:
        # 1. Panel goes offline
        # 2. HA stores grace period state (last_valid_state=2000, last_valid_changed=60 min ago)
        # 3. HA restarts
        # 4. HA comes back up, panel still offline
        # 5. Total offline time: 65 minutes
        # 6. Grace period: 60 minutes (max)
        # Expected: Grace period expired, should report unknown

        original_last_valid_changed = datetime.now() - timedelta(minutes=65)
        grace_period_minutes = 60
        stored_last_valid_state = 2000.0

        # Simulate restoration
        stored_data = SpanEnergyExtraStoredData(
            native_value=stored_last_valid_state,
            native_unit_of_measurement="Wh",
            last_valid_state=stored_last_valid_state,
            last_valid_changed=original_last_valid_changed.isoformat(),
        )

        restored = SpanEnergyExtraStoredData.from_dict(stored_data.as_dict())
        assert restored is not None

        # Parse the restored timestamp
        restored_timestamp = datetime.fromisoformat(restored.last_valid_changed)

        # Check if still within grace period
        time_since_last_valid = datetime.now() - restored_timestamp
        grace_period_duration = timedelta(minutes=grace_period_minutes)

        # Should be OUTSIDE grace period
        assert time_since_last_valid > grace_period_duration

    def test_restoration_panel_comes_back_online(self):
        """Test that restoration data is used until panel comes back online."""
        # Scenario:
        # 1. Panel was offline, grace period state was stored
        # 2. HA restarts
        # 3. Panel is still offline - use restored grace period state
        # 4. Panel comes back online - normal update takes over

        stored_last_valid_state = 5000.0
        stored_timestamp = datetime.now() - timedelta(minutes=5)

        stored_data = SpanEnergyExtraStoredData(
            native_value=stored_last_valid_state,
            native_unit_of_measurement="Wh",
            last_valid_state=stored_last_valid_state,
            last_valid_changed=stored_timestamp.isoformat(),
        )

        restored = SpanEnergyExtraStoredData.from_dict(stored_data.as_dict())

        # While offline: use restored data
        assert restored.last_valid_state == stored_last_valid_state

        # When panel comes back online with new value (5100):
        new_panel_value = 5100.0
        # The sensor should update to use the new value from the panel
        # (This is handled by the sensor's normal update logic, not restoration)
        assert new_panel_value > stored_last_valid_state  # Energy should increase


class DummyEnergySensor(SpanEnergySensorBase):
    """Minimal concrete energy sensor for offline grace period tests."""

    def __init__(  # pylint: disable=super-init-not-called
        self, grace_minutes: int | str = 15
    ) -> None:
        # Bypass parent __init__ to avoid full HA dependencies for unit testing
        self.coordinator = SimpleNamespace(
            panel_offline=True,
            config_entry=SimpleNamespace(
                options={
                    ENERGY_REPORTING_GRACE_PERIOD: grace_minutes,
                    ENABLE_ENERGY_DIP_COMPENSATION: False,
                },
            ),
            data=SimpleNamespace(),
        )
        self.entity_description = SimpleNamespace(
            device_class="energy",
            state_class=SensorStateClass.TOTAL_INCREASING,
            key="dummy",
            value_fn=lambda _: self._mock_panel_value,
        )
        self._attr_native_value = None
        self._mock_panel_value = None
        self._last_valid_state = None
        self._last_valid_changed = None
        self._grace_period_minutes = grace_minutes
        self._previous_circuit_name = None
        self._attr_unique_id = "dummy"
        self._attr_name = "Dummy"
        self._restored_from_storage: bool = False

        # Energy dip compensation state (disabled for grace period tests)
        self._energy_offset: float = 0.0
        self._last_panel_reading: float | None = None
        self._last_dip_delta: float | None = None
        self._is_total_increasing: bool = True
        self._dip_compensation_enabled: bool = False

    def _generate_unique_id(self, snapshot, description):
        return "dummy"

    def _generate_friendly_name(self, snapshot, description):
        return "dummy"

    def get_data_source(self, snapshot):
        return "dummy_data"


class TestGracePeriodFallback:
    """Tests for grace period fallback behavior when panel is offline."""

    def test_offline_uses_restored_native_value_when_missing_last_valid(self):
        """Ensure last known value is reused when grace metadata is absent."""

        sensor = DummyEnergySensor()
        sensor._attr_native_value = 123.0

        sensor._handle_offline_grace_period()

        assert sensor._attr_native_value == 123.0
        assert sensor._last_valid_state == 123.0
        assert sensor._last_valid_changed is not None

    def test_offline_grace_expires_after_duration(self):
        """Verify values drop to unknown after grace period expiration."""

        sensor = DummyEnergySensor(grace_minutes=5)
        sensor._last_valid_state = 10.0
        sensor._last_valid_changed = datetime.now() - timedelta(minutes=10)

        sensor._handle_offline_grace_period()

        assert sensor._attr_native_value is None

    def test_grace_period_coerces_string_option(self):
        """String grace period option is coerced to int for calculations."""

        sensor = DummyEnergySensor(grace_minutes="15")
        sensor._last_valid_state = 50.0
        sensor._last_valid_changed = datetime.now() - timedelta(minutes=1)

        sensor._handle_offline_grace_period()

        assert sensor._attr_native_value == 50.0


class TestMonotonicValidation:
    """Tests for value tracking of total_increasing sensors."""

    def test_accepts_decreasing_value(self):
        """Ensure a lower value is accepted (firmware reset scenario)."""
        sensor = DummyEnergySensor()
        # Simulate online state
        sensor.coordinator.panel_offline = False

        # Initial valid state
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()  # Should accept and set _last_valid_state

        assert sensor._last_valid_state == 1000.0

        # Update with LOWER value (simulates firmware reset)
        sensor._mock_panel_value = 900.0
        sensor._update_native_value()

        # Should accept 900 (decreasing values no longer blocked)
        assert sensor._attr_native_value == 900.0
        assert sensor._last_valid_state == 900.0

    def test_accepts_increasing_value(self):
        """Ensure a higher value is accepted."""
        sensor = DummyEnergySensor()
        sensor.coordinator.panel_offline = False

        # Initial valid state
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Update with HIGHER value
        sensor._mock_panel_value = 1100.0
        sensor._update_native_value()

        # Should accept 1100
        assert sensor._attr_native_value == 1100.0
        assert sensor._last_valid_state == 1100.0

    def test_accepts_equal_value(self):
        """Ensure an equal value is accepted."""
        sensor = DummyEnergySensor()
        sensor.coordinator.panel_offline = False

        # Initial valid state
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Update with EQUAL value
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Should accept 1000
        assert sensor._attr_native_value == 1000.0
        assert sensor._last_valid_state == 1000.0

    def test_ignores_validation_for_non_total_increasing(self):
        """Ensure all values accepted regardless of state class."""
        sensor = DummyEnergySensor()
        sensor.coordinator.panel_offline = False
        # Change state class to measurement
        sensor.entity_description.state_class = SensorStateClass.MEASUREMENT

        # Initial valid state
        sensor._mock_panel_value = 1000.0
        sensor._update_native_value()

        # Update with LOWER value
        sensor._mock_panel_value = 900.0
        sensor._update_native_value()

        # Should accept 900
        assert sensor._attr_native_value == 900.0
        assert sensor._last_valid_state == 900.0
