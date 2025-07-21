"""Test the Nederlandse Spoorwegen logging utilities."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen.ns_logging import (
    StructuredLogger,
    UnavailabilityLogger,
    create_component_logger,
    create_entity_logger,
    log_api_validation_result,
    log_cache_operation,
    log_config_migration,
    log_coordinator_update,
    log_data_fetch_result,
    sanitize_for_logging,
)


class TestUnavailabilityLogger:
    """Test the UnavailabilityLogger class."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def unavailability_logger(self, mock_logger):
        """Return an UnavailabilityLogger instance."""
        return UnavailabilityLogger(mock_logger, "test_entity")

    def test_init(self, mock_logger):
        """Test UnavailabilityLogger initialization."""
        logger = UnavailabilityLogger(mock_logger, "test_entity")
        assert logger._logger == mock_logger
        assert logger._entity_name == "test_entity"
        assert logger._unavailable_logged is False

    def test_log_unavailable_first_time(self, unavailability_logger, mock_logger):
        """Test logging unavailability for the first time."""
        unavailability_logger.log_unavailable("Connection lost")

        mock_logger.info.assert_called_once_with(
            "%s is unavailable: %s", "test_entity", "Connection lost"
        )
        assert unavailability_logger._unavailable_logged is True

    def test_log_unavailable_without_reason(self, unavailability_logger, mock_logger):
        """Test logging unavailability without reason."""
        unavailability_logger.log_unavailable()

        mock_logger.info.assert_called_once_with("%s is unavailable", "test_entity")
        assert unavailability_logger._unavailable_logged is True

    def test_log_unavailable_already_logged(self, unavailability_logger, mock_logger):
        """Test logging unavailability when already logged."""
        # First call should log
        unavailability_logger.log_unavailable("First error")
        assert mock_logger.info.call_count == 1

        # Second call should not log
        unavailability_logger.log_unavailable("Second error")
        assert mock_logger.info.call_count == 1  # Still 1

    def test_log_recovery_when_unavailable_logged(
        self, unavailability_logger, mock_logger
    ):
        """Test logging recovery when unavailability was logged."""
        # First mark as unavailable
        unavailability_logger.log_unavailable("Error")
        mock_logger.info.reset_mock()

        # Then log recovery
        unavailability_logger.log_recovery()

        mock_logger.info.assert_called_once_with("%s is back online", "test_entity")
        assert unavailability_logger._unavailable_logged is False

    def test_log_recovery_when_not_unavailable(
        self, unavailability_logger, mock_logger
    ):
        """Test logging recovery when not marked as unavailable."""
        unavailability_logger.log_recovery()

        # Should not log anything
        mock_logger.info.assert_not_called()
        assert unavailability_logger._unavailable_logged is False

    def test_reset(self, unavailability_logger):
        """Test resetting unavailability state."""
        # Mark as unavailable
        unavailability_logger._unavailable_logged = True

        # Reset
        unavailability_logger.reset()

        assert unavailability_logger._unavailable_logged is False

    def test_is_unavailable_logged_property(self, unavailability_logger):
        """Test is_unavailable_logged property."""
        assert unavailability_logger.is_unavailable_logged is False

        unavailability_logger._unavailable_logged = True
        assert unavailability_logger.is_unavailable_logged is True


class TestStructuredLogger:
    """Test the StructuredLogger class."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def structured_logger(self, mock_logger):
        """Return a StructuredLogger instance."""
        return StructuredLogger(mock_logger, "test_component")

    def test_init(self, mock_logger):
        """Test StructuredLogger initialization."""
        logger = StructuredLogger(mock_logger, "test_component")
        assert logger._logger == mock_logger
        assert logger._component == "test_component"

    def test_debug_api_call_simple(self, structured_logger, mock_logger):
        """Test debug_api_call without details."""
        structured_logger.debug_api_call("get_stations")

        expected_context = {"component": "test_component", "operation": "get_stations"}
        mock_logger.debug.assert_called_once_with(
            "API call: %s", "get_stations", extra=expected_context
        )

    def test_debug_api_call_with_details(self, structured_logger, mock_logger):
        """Test debug_api_call with details."""
        details = {"station": "AMS", "count": 5}
        structured_logger.debug_api_call("get_departures", details)

        expected_context = {
            "component": "test_component",
            "operation": "get_departures",
            "station": "AMS",
            "count": 5,
        }
        mock_logger.debug.assert_called_once_with(
            "API call: %s", "get_departures", extra=expected_context
        )

    def test_info_setup_simple(self, structured_logger, mock_logger):
        """Test info_setup without entry_id."""
        structured_logger.info_setup("Integration loaded")

        expected_context = {"component": "test_component"}
        mock_logger.info.assert_called_once_with(
            "Setup: %s", "Integration loaded", extra=expected_context
        )

    def test_info_setup_with_entry_id(self, structured_logger, mock_logger):
        """Test info_setup with entry_id."""
        structured_logger.info_setup("Entry configured", "entry_123")

        expected_context = {"component": "test_component", "entry_id": "entry_123"}
        mock_logger.info.assert_called_once_with(
            "Setup: %s", "Entry configured", extra=expected_context
        )

    def test_warning_validation_simple(self, structured_logger, mock_logger):
        """Test warning_validation without data."""
        structured_logger.warning_validation("Invalid station code")

        expected_context = {"component": "test_component", "validation_error": True}
        mock_logger.warning.assert_called_once_with(
            "Validation: %s", "Invalid station code", extra=expected_context
        )

    def test_warning_validation_with_data(self, structured_logger, mock_logger):
        """Test warning_validation with data."""
        structured_logger.warning_validation("Invalid format", {"code": "INVALID"})

        expected_context = {
            "component": "test_component",
            "validation_error": True,
            "invalid_data": "{'code': 'INVALID'}",
        }
        mock_logger.warning.assert_called_once_with(
            "Validation: %s", "Invalid format", extra=expected_context
        )

    def test_error_api_simple(self, structured_logger, mock_logger):
        """Test error_api without details."""
        error = ConnectionError("Network failed")
        structured_logger.error_api("get_stations", error)

        expected_context = {
            "component": "test_component",
            "operation": "get_stations",
            "error_type": "ConnectionError",
        }
        mock_logger.error.assert_called_once_with(
            "API error in %s: %s", "get_stations", error, extra=expected_context
        )

    def test_error_api_with_details(self, structured_logger, mock_logger):
        """Test error_api with details."""
        error = ValueError("Invalid parameter")
        details = {"station": "AMS", "retry_count": 3}
        structured_logger.error_api("get_departures", error, details)

        expected_context = {
            "component": "test_component",
            "operation": "get_departures",
            "error_type": "ValueError",
            "station": "AMS",
            "retry_count": 3,
        }
        mock_logger.error.assert_called_once_with(
            "API error in %s: %s", "get_departures", error, extra=expected_context
        )

    def test_debug_data_processing_simple(self, structured_logger, mock_logger):
        """Test debug_data_processing without count."""
        structured_logger.debug_data_processing("filtering_trips")

        expected_context = {
            "component": "test_component",
            "operation": "filtering_trips",
        }
        mock_logger.debug.assert_called_once_with(
            "Data processing: filtering_trips", extra=expected_context
        )

    def test_debug_data_processing_with_count(self, structured_logger, mock_logger):
        """Test debug_data_processing with count."""
        structured_logger.debug_data_processing("parsing_stations", 25)

        expected_context = {
            "component": "test_component",
            "operation": "parsing_stations",
            "item_count": 25,
        }
        mock_logger.debug.assert_called_once_with(
            "Data processing: parsing_stations (25 items)", extra=expected_context
        )


class TestLoggingUtilities:
    """Test standalone logging utility functions."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger."""
        return MagicMock(spec=logging.Logger)

    def test_create_entity_logger(self):
        """Test create_entity_logger function."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger_instance = MagicMock()
            mock_get_logger.return_value = mock_logger_instance

            logger = create_entity_logger("test_sensor")

            mock_get_logger.assert_called_once_with(
                "homeassistant.components.nederlandse_spoorwegen.test_sensor"
            )
            assert isinstance(logger, UnavailabilityLogger)
            assert logger._logger == mock_logger_instance
            assert logger._entity_name == "test_sensor"

    def test_create_component_logger(self):
        """Test create_component_logger function."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger_instance = MagicMock()
            mock_get_logger.return_value = mock_logger_instance

            logger = create_component_logger("coordinator")

            mock_get_logger.assert_called_once_with(
                "homeassistant.components.nederlandse_spoorwegen.coordinator"
            )
            assert isinstance(logger, StructuredLogger)
            assert logger._logger == mock_logger_instance
            assert logger._component == "coordinator"

    def test_log_api_validation_result_success(self, mock_logger):
        """Test log_api_validation_result with success."""
        log_api_validation_result(mock_logger, True)

        mock_logger.debug.assert_called_once_with("API validation successful")

    def test_log_api_validation_result_failure_with_error(self, mock_logger):
        """Test log_api_validation_result with failure and error."""
        error = ConnectionError("Network failed")
        log_api_validation_result(mock_logger, False, error)

        mock_logger.debug.assert_called_once_with(
            "API validation failed: %s - %s", "ConnectionError", error
        )

    def test_log_api_validation_result_failure_no_error(self, mock_logger):
        """Test log_api_validation_result with failure and no error."""
        log_api_validation_result(mock_logger, False)

        mock_logger.debug.assert_called_once_with(
            "API validation failed: %s - %s", "Unknown", None
        )

    def test_log_config_migration(self, mock_logger):
        """Test log_config_migration function."""
        log_config_migration(mock_logger, "entry_123", 5)

        mock_logger.info.assert_called_once_with(
            "Migrated legacy routes for entry %s: %d routes processed", "entry_123", 5
        )

    def test_log_data_fetch_result_success_with_count(self, mock_logger):
        """Test log_data_fetch_result with success and count."""
        log_data_fetch_result(mock_logger, "fetch_stations", True, 25)

        mock_logger.debug.assert_called_once_with(
            "%s successful: %d items retrieved", "fetch_stations", 25
        )

    def test_log_data_fetch_result_success_no_count(self, mock_logger):
        """Test log_data_fetch_result with success and no count."""
        log_data_fetch_result(mock_logger, "fetch_stations", True)

        mock_logger.debug.assert_called_once_with("%s successful", "fetch_stations")

    def test_log_data_fetch_result_failure_with_error(self, mock_logger):
        """Test log_data_fetch_result with failure and error."""
        error = ValueError("Invalid data")
        log_data_fetch_result(mock_logger, "fetch_stations", False, error=error)

        mock_logger.error.assert_called_once_with(
            "%s failed: %s", "fetch_stations", "Invalid data"
        )

    def test_log_data_fetch_result_failure_no_error(self, mock_logger):
        """Test log_data_fetch_result with failure and no error."""
        log_data_fetch_result(mock_logger, "fetch_stations", False)

        mock_logger.error.assert_called_once_with(
            "%s failed: %s", "fetch_stations", "Unknown error"
        )

    def test_log_cache_operation_success_with_details(self, mock_logger):
        """Test log_cache_operation with success and details."""
        log_cache_operation(mock_logger, "update", "station", True, "25 items cached")

        mock_logger.debug.assert_called_once_with(
            "station cache update: 25 items cached"
        )

    def test_log_cache_operation_success_no_details(self, mock_logger):
        """Test log_cache_operation with success and no details."""
        log_cache_operation(mock_logger, "clear", "route", True)

        mock_logger.debug.assert_called_once_with("route cache clear")

    def test_log_cache_operation_failure(self, mock_logger):
        """Test log_cache_operation with failure."""
        log_cache_operation(mock_logger, "update", "station", False, "failed to write")

        mock_logger.warning.assert_called_once_with(
            "station cache update: failed to write"
        )

    def test_log_coordinator_update_simple(self, mock_logger):
        """Test log_coordinator_update with minimal parameters."""
        log_coordinator_update(mock_logger, "refresh")

        mock_logger.debug.assert_called_once_with("Coordinator update: refresh")

    def test_log_coordinator_update_with_route_count(self, mock_logger):
        """Test log_coordinator_update with route count."""
        log_coordinator_update(mock_logger, "refresh", route_count=5)

        mock_logger.debug.assert_called_once_with(
            "Coordinator update: refresh (5 routes)"
        )

    def test_log_coordinator_update_with_duration(self, mock_logger):
        """Test log_coordinator_update with duration."""
        log_coordinator_update(mock_logger, "refresh", duration=2.5)

        mock_logger.debug.assert_called_once_with(
            "Coordinator update: refresh completed in 2.500s"
        )

    def test_log_coordinator_update_full_params(self, mock_logger):
        """Test log_coordinator_update with all parameters."""
        log_coordinator_update(mock_logger, "refresh", route_count=3, duration=1.25)

        mock_logger.debug.assert_called_once_with(
            "Coordinator update: refresh (3 routes) completed in 1.250s"
        )

    def test_sanitize_for_logging_none(self):
        """Test sanitize_for_logging with None."""
        result = sanitize_for_logging(None)
        assert result == "None"

    def test_sanitize_for_logging_short_string(self):
        """Test sanitize_for_logging with short string."""
        result = sanitize_for_logging("Hello World")
        assert result == "Hello World"

    def test_sanitize_for_logging_long_string(self):
        """Test sanitize_for_logging with long string."""
        long_string = "A" * 150
        result = sanitize_for_logging(long_string)
        assert result == "A" * 100 + "..."

    def test_sanitize_for_logging_custom_length(self):
        """Test sanitize_for_logging with custom max length."""
        result = sanitize_for_logging("Hello World", max_length=5)
        assert result == "Hello..."

    def test_sanitize_for_logging_complex_object(self):
        """Test sanitize_for_logging with complex object."""
        data = {"key": "value", "number": 42}
        result = sanitize_for_logging(data)
        assert result == "{'key': 'value', 'number': 42}"

    def test_sanitize_for_logging_exact_length(self):
        """Test sanitize_for_logging with exact max length."""
        data = "A" * 100
        result = sanitize_for_logging(data, max_length=100)
        assert result == "A" * 100  # Should not be truncated
