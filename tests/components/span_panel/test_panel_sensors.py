"""Test panel-level sensors functionality."""

from unittest.mock import MagicMock

import pytest
from span_panel_api import SpanPanelSnapshot

from homeassistant.components.span_panel.const import (
    DSM_OFF_GRID,
    DSM_ON_GRID,
    PANEL_ON_GRID,
)
from homeassistant.components.span_panel.sensor import (
    SpanPanelPanelStatus,
    SpanPanelStatus,
)
from homeassistant.components.span_panel.sensor_definitions import (
    PANEL_DATA_STATUS_SENSORS,
    STATUS_SENSORS,
)

from .factories import SpanPanelSnapshotFactory
from .helpers import make_span_panel_entry


class TestPanelSensors:
    """Test panel-level sensors."""

    @pytest.fixture
    def mock_snapshot(self) -> SpanPanelSnapshot:
        """Create a snapshot for testing."""
        return SpanPanelSnapshotFactory.create_complete()

    @pytest.fixture
    def mock_coordinator(self, mock_snapshot: SpanPanelSnapshot) -> MagicMock:
        """Create a mock coordinator for testing."""
        coordinator = MagicMock()
        coordinator.data = mock_snapshot
        coordinator.config_entry = make_span_panel_entry()
        return coordinator

    def test_panel_data_status_sensors_creation(
        self, mock_coordinator: MagicMock, mock_snapshot: SpanPanelSnapshot
    ) -> None:
        """Test that panel data status sensors are created correctly."""
        for description in PANEL_DATA_STATUS_SENSORS:
            sensor = SpanPanelPanelStatus(mock_coordinator, description, mock_snapshot)
            assert sensor.entity_description == description
            assert sensor.coordinator == mock_coordinator

            # Panel data sensors return the snapshot itself as data source
            data_source = sensor.get_data_source(mock_snapshot)
            assert data_source is mock_snapshot

    def test_hardware_status_sensors_creation(
        self, mock_coordinator: MagicMock, mock_snapshot: SpanPanelSnapshot
    ) -> None:
        """Test that hardware status sensors are created correctly."""
        for description in STATUS_SENSORS:
            sensor = SpanPanelStatus(mock_coordinator, description, mock_snapshot)
            assert sensor.entity_description == description
            assert sensor.coordinator == mock_coordinator

            # Status sensors also return the snapshot
            data_source = sensor.get_data_source(mock_snapshot)
            assert data_source is mock_snapshot

    def test_main_relay_state_sensor(self) -> None:
        """Test the main relay state sensor specifically."""
        main_relay_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "main_relay_state"
        )

        test_cases = (
            ("CLOSED", "CLOSED"),
            ("OPEN", "OPEN"),
            ("UNKNOWN", "UNKNOWN"),
        )

        for input_state, expected_output in test_cases:
            snapshot = SpanPanelSnapshotFactory.create(main_relay_state=input_state)
            sensor_value = main_relay_description.value_fn(snapshot)
            assert sensor_value == expected_output, (
                f"Expected {expected_output} for input {input_state}, got {sensor_value}"
            )

    def test_grid_forming_entity_sensor(self) -> None:
        """Test the grid forming entity sensor."""
        description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "grid_forming_entity"
        )

        for source in ("GRID", "BATTERY", "PV", "GENERATOR", "NONE"):
            snapshot = SpanPanelSnapshotFactory.create(dominant_power_source=source)
            assert description.value_fn(snapshot) == source

        # None defaults to "unknown"
        snapshot_none = SpanPanelSnapshotFactory.create(dominant_power_source=None)
        assert description.value_fn(snapshot_none) == "unknown"

    def test_vendor_cloud_sensor(self) -> None:
        """Test the vendor cloud sensor."""
        description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "vendor_cloud"
        )

        for state in ("CONNECTED", "UNCONNECTED"):
            snapshot = SpanPanelSnapshotFactory.create(vendor_cloud=state)
            assert description.value_fn(snapshot) == state

        # None defaults to "unknown"
        snapshot_none = SpanPanelSnapshotFactory.create(vendor_cloud=None)
        assert description.value_fn(snapshot_none) == "unknown"

    def test_software_version_sensor(self) -> None:
        """Test the software version sensor."""
        version_description = next(
            d for d in STATUS_SENSORS if d.key == "software_version"
        )

        for version in ("1.2.3", "2.0.1", "1.5.0-beta"):
            snapshot = SpanPanelSnapshotFactory.create(firmware_version=version)
            assert version_description.value_fn(snapshot) == version

    def test_current_run_config_sensor(self) -> None:
        """Test the current run config sensor."""
        config_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "current_run_config"
        )

        snapshot = SpanPanelSnapshotFactory.create(current_run_config=PANEL_ON_GRID)
        assert config_description.value_fn(snapshot) == PANEL_ON_GRID

    def test_sensor_unique_ids(
        self, mock_coordinator: MagicMock, mock_snapshot: SpanPanelSnapshot
    ) -> None:
        """Test that sensors have correct unique IDs."""
        main_relay_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "main_relay_state"
        )

        sensor = SpanPanelPanelStatus(
            mock_coordinator, main_relay_description, mock_snapshot
        )
        expected_unique_id = (
            f"span_{mock_snapshot.serial_number.lower()}_{main_relay_description.key}"
        )
        assert sensor.unique_id == expected_unique_id

    def test_sensor_translation_keys(
        self, mock_coordinator: MagicMock, mock_snapshot: SpanPanelSnapshot
    ) -> None:
        """Test that panel sensors have translation keys set."""
        for description in PANEL_DATA_STATUS_SENSORS:
            sensor = SpanPanelPanelStatus(mock_coordinator, description, mock_snapshot)
            assert description.translation_key is not None
            assert (
                sensor.entity_description.translation_key == description.translation_key
            )

        for description in STATUS_SENSORS:
            sensor = SpanPanelStatus(mock_coordinator, description, mock_snapshot)
            assert description.translation_key is not None
            assert (
                sensor.entity_description.translation_key == description.translation_key
            )

    def test_main_relay_state_with_real_data(self) -> None:
        """Test main relay state sensor with real snapshot data."""
        main_relay_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "main_relay_state"
        )

        snapshot_closed = SpanPanelSnapshotFactory.create(main_relay_state="CLOSED")
        assert main_relay_description.value_fn(snapshot_closed) == "CLOSED"

        snapshot_open = SpanPanelSnapshotFactory.create(main_relay_state="OPEN")
        assert main_relay_description.value_fn(snapshot_open) == "OPEN"

    def test_dsm_state_with_real_data(self) -> None:
        """Test DSM state sensor with real snapshot data."""
        dsm_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "dsm_state"
        )

        snapshot_on = SpanPanelSnapshotFactory.create(dsm_state=DSM_ON_GRID)
        assert dsm_description.value_fn(snapshot_on) == DSM_ON_GRID

        snapshot_off = SpanPanelSnapshotFactory.create(dsm_state=DSM_OFF_GRID)
        assert dsm_description.value_fn(snapshot_off) == DSM_OFF_GRID

    def test_software_version_extra_state_attributes_panel_size(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test that panel_size is always present in extra_state_attributes."""
        description = next(d for d in STATUS_SENSORS if d.key == "software_version")

        snapshot_with_size = SpanPanelSnapshotFactory.create(panel_size=32)
        mock_coordinator.data = snapshot_with_size
        sensor = SpanPanelStatus(mock_coordinator, description, snapshot_with_size)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["panel_size"] == 32

    def test_software_version_extra_state_attributes_wifi_ssid(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test that wifi_ssid appears in extra_state_attributes when present."""
        description = next(d for d in STATUS_SENSORS if d.key == "software_version")

        snapshot = SpanPanelSnapshotFactory.create(panel_size=24, wifi_ssid="MyNetwork")
        mock_coordinator.data = snapshot
        sensor = SpanPanelStatus(mock_coordinator, description, snapshot)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["panel_size"] == 24
        assert attrs["wifi_ssid"] == "MyNetwork"

    def test_software_version_extra_state_attributes_no_wifi(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Test that wifi_ssid is omitted when None."""
        description = next(d for d in STATUS_SENSORS if d.key == "software_version")

        snapshot = SpanPanelSnapshotFactory.create(panel_size=16, wifi_ssid=None)
        mock_coordinator.data = snapshot
        sensor = SpanPanelStatus(mock_coordinator, description, snapshot)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "wifi_ssid" not in attrs
        assert attrs["panel_size"] == 16

    def test_dsm_grid_state_deprecated_alias(self) -> None:
        """Test DSM Grid State reads from dsm_state (deprecated alias)."""
        dsm_grid_description = next(
            d for d in PANEL_DATA_STATUS_SENSORS if d.key == "dsm_grid_state"
        )

        snapshot = SpanPanelSnapshotFactory.create(dsm_state=DSM_ON_GRID)
        assert dsm_grid_description.value_fn(snapshot) == DSM_ON_GRID


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
