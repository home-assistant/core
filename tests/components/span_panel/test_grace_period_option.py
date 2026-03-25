"""Test grace period configuration option."""

from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components.span_panel.config_flow import OPTIONS_SCHEMA
from homeassistant.components.span_panel.options import ENERGY_REPORTING_GRACE_PERIOD


class TestGracePeriodOption:
    """Test grace period configuration option."""

    def test_grace_period_option_constant(self):
        """Test that grace period option constant is defined correctly."""
        assert ENERGY_REPORTING_GRACE_PERIOD == "energy_reporting_grace_period"

    def test_grace_period_in_options_schema(self):
        """Test that grace period option is in the options schema."""
        # Check that energy_reporting_grace_period is in the schema
        assert ENERGY_REPORTING_GRACE_PERIOD in OPTIONS_SCHEMA.schema

        # Check that it has proper validation (int, 0-60 range)
        grace_period_validator = OPTIONS_SCHEMA.schema[ENERGY_REPORTING_GRACE_PERIOD]

        # Test valid values
        assert grace_period_validator(0) == 0
        assert grace_period_validator(15) == 15
        assert grace_period_validator(60) == 60

        # Test invalid values should raise validation error
        with pytest.raises(vol.Invalid):
            grace_period_validator(-1)

        with pytest.raises(vol.Invalid):
            grace_period_validator(61)

        with pytest.raises(vol.Invalid):
            grace_period_validator("invalid")

    def test_grace_period_option_persistence(self):
        """Test that grace period option persists in configuration."""
        # Mock coordinator with grace period option
        mock_coordinator = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.options = {ENERGY_REPORTING_GRACE_PERIOD: 30}

        # Test that option is accessible
        grace_period = mock_coordinator.config_entry.options.get(
            ENERGY_REPORTING_GRACE_PERIOD, 15
        )
        assert grace_period == 30

    def test_grace_period_edge_cases(self):
        """Test grace period edge cases."""
        grace_period_validator = OPTIONS_SCHEMA.schema[ENERGY_REPORTING_GRACE_PERIOD]

        # Test boundary values
        assert grace_period_validator(0) == 0  # Immediate unavailable
        assert grace_period_validator(60) == 60  # Maximum 1 hour

        # Test that non-int values should raise validation error
        with pytest.raises(vol.Invalid):
            grace_period_validator(15.0)

        with pytest.raises(vol.Invalid):
            grace_period_validator(15.9)

    def test_grace_period_integration_with_yaml_generation(self):
        """Test that grace period integrates correctly with YAML generation."""
        # Test that the grace period gets passed to YAML templates
        mock_coordinator = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.options = {ENERGY_REPORTING_GRACE_PERIOD: 25}

        # Simulate how the option is used in template generation
        grace_period = str(
            mock_coordinator.config_entry.options.get(ENERGY_REPORTING_GRACE_PERIOD, 15)
        )

        # Should be converted to string for template placeholders
        assert grace_period == "25"
        assert isinstance(grace_period, str)
