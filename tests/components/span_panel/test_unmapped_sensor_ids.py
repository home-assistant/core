"""Tests for unmapped circuit sensor ID generation."""

from unittest.mock import MagicMock

from span_panel_api import SpanPanelSnapshot

from homeassistant.components.span_panel.const import USE_DEVICE_PREFIX
from homeassistant.components.span_panel.sensor import SpanUnmappedCircuitSensor
from homeassistant.components.span_panel.sensor_definitions import UNMAPPED_SENSORS
from homeassistant.const import CONF_HOST

from .factories import SpanPanelSnapshotFactory

from tests.common import MockConfigEntry


class TestUnmappedSensorIds:
    """Test unique ID and entity ID generation for unmapped circuit sensors."""

    TEST_SERIAL_NUMBER = "NJ-2316-005K6"

    def _create_snapshot(self, serial_number: str | None = None) -> SpanPanelSnapshot:
        """Create a SpanPanelSnapshot with predefined data."""
        if serial_number is None:
            serial_number = self.TEST_SERIAL_NUMBER
        return SpanPanelSnapshotFactory.create(serial_number=serial_number)

    def _create_mock_coordinator(
        self, config_options: dict[str, object] | None = None
    ) -> MagicMock:
        """Create a mock coordinator with config entry."""
        if config_options is None:
            config_options = {}

        coordinator = MagicMock()
        coordinator.config_entry = MockConfigEntry(
            domain="span_panel",
            data={CONF_HOST: "192.168.1.100", "device_name": "SPAN Panel"},
            options=config_options,
            title="SPAN Panel",
        )
        return coordinator

    def test_unmapped_sensor_unique_id_generation(self) -> None:
        """Test that unmapped circuit sensors generate correct unique IDs."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        expected_patterns = {
            "instantPowerW": f"span_{self.TEST_SERIAL_NUMBER.lower()}_unmapped_tab_32_power",
            "producedEnergyWh": f"span_{self.TEST_SERIAL_NUMBER.lower()}_unmapped_tab_32_energy_produced",
            "consumedEnergyWh": f"span_{self.TEST_SERIAL_NUMBER.lower()}_unmapped_tab_32_energy_consumed",
        }

        for description in UNMAPPED_SENSORS:
            sensor = SpanUnmappedCircuitSensor(
                coordinator, description, snapshot, circuit_id
            )

            actual_unique_id = sensor._attr_unique_id
            expected_unique_id = expected_patterns[description.key]

            assert actual_unique_id == expected_unique_id, (
                f"Unique ID mismatch for {description.key}: "
                f"expected {expected_unique_id}, got {actual_unique_id}"
            )

            assert "unmapped_tab_32_unmapped_tab_32" not in actual_unique_id, (
                f"Duplicate unmapped_tab in unique_id: {actual_unique_id}"
            )

            method_unique_id = sensor._generate_unique_id(snapshot, description)
            assert method_unique_id == expected_unique_id

    def test_unmapped_sensor_entity_id_generation(self) -> None:
        """Test that unmapped circuit sensors have proper unique IDs."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        for description in UNMAPPED_SENSORS:
            sensor = SpanUnmappedCircuitSensor(
                coordinator, description, snapshot, circuit_id
            )

            assert sensor.unique_id is not None
            assert "unmapped_tab_32" in sensor.unique_id
            assert "power" in sensor.unique_id or "energy" in sensor.unique_id

    def test_unmapped_sensor_always_uses_device_prefix(self) -> None:
        """Test that unmapped sensors always use device prefix regardless of config."""
        snapshot = self._create_snapshot()
        circuit_id = "unmapped_tab_27"

        coordinator_no_prefix = self._create_mock_coordinator(
            {USE_DEVICE_PREFIX: False}
        )
        coordinator_with_prefix = self._create_mock_coordinator(
            {USE_DEVICE_PREFIX: True}
        )

        for description in UNMAPPED_SENSORS:
            sensor_no_prefix = SpanUnmappedCircuitSensor(
                coordinator_no_prefix, description, snapshot, circuit_id
            )
            sensor_with_prefix = SpanUnmappedCircuitSensor(
                coordinator_with_prefix, description, snapshot, circuit_id
            )

            assert sensor_no_prefix.unique_id == sensor_with_prefix.unique_id
            assert "span_" in sensor_no_prefix.unique_id

    def test_unmapped_sensor_different_circuit_numbers(self) -> None:
        """Test unmapped sensors with different circuit numbers."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()

        for circuit_id in ("unmapped_tab_15", "unmapped_tab_30", "unmapped_tab_28"):
            for description in UNMAPPED_SENSORS:
                sensor = SpanUnmappedCircuitSensor(
                    coordinator, description, snapshot, circuit_id
                )

                unique_id = sensor._generate_unique_id(snapshot, description)
                assert circuit_id in unique_id
                assert f"{circuit_id}_{circuit_id}" not in unique_id

    def test_unmapped_sensor_different_serial_numbers(self) -> None:
        """Test unmapped sensors with different panel serial numbers."""
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        for serial_number in ("ABC123DEF456", "XYZ789GHI012", "TEST-SERIAL-001"):
            snapshot = self._create_snapshot(serial_number)

            for description in UNMAPPED_SENSORS:
                sensor = SpanUnmappedCircuitSensor(
                    coordinator, description, snapshot, circuit_id
                )
                unique_id = sensor._generate_unique_id(snapshot, description)

                assert serial_number.lower() in unique_id
                assert unique_id.startswith(f"span_{serial_number.lower()}_")

    def test_unmapped_sensor_key_mapping(self) -> None:
        """Test that description keys are correctly mapped to user-friendly suffixes."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        key_to_suffix_mapping = {
            "instantPowerW": "power",
            "producedEnergyWh": "energy_produced",
            "consumedEnergyWh": "energy_consumed",
        }

        for description in UNMAPPED_SENSORS:
            sensor = SpanUnmappedCircuitSensor(
                coordinator, description, snapshot, circuit_id
            )
            unique_id = sensor._generate_unique_id(snapshot, description)
            expected_suffix = key_to_suffix_mapping[description.key]

            assert expected_suffix in unique_id

    def test_unmapped_sensor_entity_registry_defaults(self) -> None:
        """Test that unmapped sensors have correct entity registry defaults."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        for description in UNMAPPED_SENSORS:
            sensor = SpanUnmappedCircuitSensor(
                coordinator, description, snapshot, circuit_id
            )
            assert sensor._attr_entity_registry_enabled_default is True
            assert sensor._attr_entity_registry_visible_default is False

    def test_unmapped_sensor_initialization_bug_prevention(self) -> None:
        """Prevent the bug where description.key gets overridden during initialization."""
        snapshot = self._create_snapshot()
        coordinator = self._create_mock_coordinator()
        circuit_id = "unmapped_tab_32"

        for description in UNMAPPED_SENSORS:
            sensor = SpanUnmappedCircuitSensor(
                coordinator, description, snapshot, circuit_id
            )

            assert hasattr(sensor, "original_key")
            assert sensor.original_key == description.key

            unique_id = sensor._attr_unique_id
            assert "unmapped_tab_32_unmapped_tab_32" not in unique_id

            expected_suffix = {
                "instantPowerW": "power",
                "producedEnergyWh": "energy_produced",
                "consumedEnergyWh": "energy_consumed",
            }[description.key]

            assert expected_suffix in unique_id
