"""Test snapshot update interval configuration option."""

from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.span_panel.config_flow import OPTIONS_SCHEMA
from homeassistant.components.span_panel.const import DEFAULT_SNAPSHOT_INTERVAL
from homeassistant.components.span_panel.options import SNAPSHOT_UPDATE_INTERVAL


class TestSnapshotIntervalOption:
    """Test snapshot update interval configuration option."""

    def test_snapshot_interval_constant(self) -> None:
        """Test that the option constant is defined correctly."""
        assert SNAPSHOT_UPDATE_INTERVAL == "snapshot_update_interval"

    def test_default_snapshot_interval(self) -> None:
        """Test that the default interval is 5.0 seconds."""
        assert DEFAULT_SNAPSHOT_INTERVAL == 5.0

    def test_snapshot_interval_in_options_schema(self) -> None:
        """Test that snapshot interval is in the OPTIONS_SCHEMA."""
        assert SNAPSHOT_UPDATE_INTERVAL in OPTIONS_SCHEMA.schema

    def test_snapshot_interval_valid_values(self) -> None:
        """Test that valid values pass validation."""
        validator = OPTIONS_SCHEMA.schema[SNAPSHOT_UPDATE_INTERVAL]

        assert validator(0) == 0.0
        assert validator(0.5) == 0.5
        assert validator(1) == 1.0
        assert validator(1.0) == 1.0
        assert validator(5) == 5.0
        assert validator(15) == 15.0

    def test_snapshot_interval_coerces_int_to_float(self) -> None:
        """Test that integer input is coerced to float."""
        validator = OPTIONS_SCHEMA.schema[SNAPSHOT_UPDATE_INTERVAL]
        result = validator(3)
        assert isinstance(result, float)
        assert result == 3.0

    def test_snapshot_interval_rejects_negative(self) -> None:
        """Test that negative values are rejected."""
        validator = OPTIONS_SCHEMA.schema[SNAPSHOT_UPDATE_INTERVAL]
        with pytest.raises(vol.Invalid):
            validator(-1)

    def test_snapshot_interval_rejects_above_max(self) -> None:
        """Test that values above 15 are rejected."""
        validator = OPTIONS_SCHEMA.schema[SNAPSHOT_UPDATE_INTERVAL]
        with pytest.raises(vol.Invalid):
            validator(16)

        with pytest.raises(vol.Invalid):
            validator(100)

    def test_snapshot_interval_rejects_non_numeric(self) -> None:
        """Test that non-numeric values are rejected."""
        validator = OPTIONS_SCHEMA.schema[SNAPSHOT_UPDATE_INTERVAL]
        with pytest.raises(vol.Invalid):
            validator("invalid")

    def test_snapshot_interval_option_persistence(self) -> None:
        """Test that the option is accessible from config entry options."""
        mock_coordinator = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.options = {
            SNAPSHOT_UPDATE_INTERVAL: 5.0,
        }

        interval = mock_coordinator.config_entry.options.get(
            SNAPSHOT_UPDATE_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL
        )
        assert interval == 5.0

    def test_snapshot_interval_default_when_missing(self) -> None:
        """Test that the default is used when option is not set."""
        mock_coordinator = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.options = {}

        interval = mock_coordinator.config_entry.options.get(
            SNAPSHOT_UPDATE_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL
        )
        assert interval == DEFAULT_SNAPSHOT_INTERVAL
        assert interval == 5.0
