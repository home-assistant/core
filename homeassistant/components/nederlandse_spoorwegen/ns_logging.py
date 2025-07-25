"""Centralized logging utilities for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class UnavailabilityLogger:
    """Manages unavailability logging pattern for entities."""

    def __init__(self, logger: logging.Logger, entity_name: str) -> None:
        """Initialize unavailability logger."""
        self._logger = logger
        self._entity_name = entity_name
        self._unavailable_logged = False

    def log_unavailable(self, reason: str | None = None) -> None:
        """Log entity unavailability once."""
        if not self._unavailable_logged:
            if reason:
                self._logger.info("%s is unavailable: %s", self._entity_name, reason)
            else:
                self._logger.info("%s is unavailable", self._entity_name)
            self._unavailable_logged = True

    def log_recovery(self) -> None:
        """Log entity recovery."""
        if self._unavailable_logged:
            self._logger.info("%s is back online", self._entity_name)
            self._unavailable_logged = False

    def reset(self) -> None:
        """Reset unavailability state."""
        self._unavailable_logged = False

    @property
    def is_unavailable_logged(self) -> bool:
        """Return if unavailability has been logged."""
        return self._unavailable_logged


class StructuredLogger:
    """Provides structured logging with consistent context."""

    def __init__(self, logger: logging.Logger, component: str) -> None:
        """Initialize structured logger."""
        self._logger = logger
        self._component = component

    def debug_api_call(
        self, operation: str, details: dict[str, Any] | None = None
    ) -> None:
        """Log API call with structured context."""
        context: dict[str, Any] = {"component": self._component, "operation": operation}
        if details:
            context.update(details)
        self._logger.debug("API call: %s", operation, extra=context)

    def info_setup(self, message: str, entry_id: str | None = None) -> None:
        """Log setup information with context."""
        context: dict[str, Any] = {"component": self._component}
        if entry_id:
            context["entry_id"] = entry_id
        self._logger.info("Setup: %s", message, extra=context)

    def warning_validation(self, message: str, data: Any = None) -> None:
        """Log validation warning with context."""
        context: dict[str, Any] = {
            "component": self._component,
            "validation_error": True,
        }
        if data is not None:
            context["invalid_data"] = str(data)
        self._logger.warning("Validation: %s", message, extra=context)

    def error_api(
        self, operation: str, error: Exception, details: dict[str, Any] | None = None
    ) -> None:
        """Log API error with structured context."""
        context: dict[str, Any] = {
            "component": self._component,
            "operation": operation,
            "error_type": type(error).__name__,
        }
        if details:
            context.update(details)
        self._logger.error("API error in %s: %s", operation, error, extra=context)

    def debug_data_processing(self, operation: str, count: int | None = None) -> None:
        """Log data processing with context."""
        context: dict[str, Any] = {"component": self._component, "operation": operation}
        if count is not None:
            context["item_count"] = count
        message = f"Data processing: {operation}"
        if count is not None:
            message += f" ({count} items)"
        self._logger.debug(message, extra=context)


def create_entity_logger(entity_id: str) -> UnavailabilityLogger:
    """Create an unavailability logger for an entity."""
    logger = logging.getLogger(
        f"homeassistant.components.nederlandse_spoorwegen.{entity_id}"
    )
    return UnavailabilityLogger(logger, entity_id)


def create_component_logger(component: str) -> StructuredLogger:
    """Create a structured logger for a component."""
    logger = logging.getLogger(
        f"homeassistant.components.nederlandse_spoorwegen.{component}"
    )
    return StructuredLogger(logger, component)


def log_api_validation_result(
    logger: logging.Logger, success: bool, error: Exception | None = None
) -> None:
    """Log API validation result with consistent format."""
    if success:
        logger.debug("API validation successful")
    else:
        error_type = type(error).__name__ if error else "Unknown"
        logger.debug("API validation failed: %s - %s", error_type, error)


def log_config_migration(
    logger: logging.Logger, entry_id: str, route_count: int
) -> None:
    """Log configuration migration with consistent format."""
    logger.info(
        "Migrated legacy routes for entry %s: %d routes processed",
        entry_id,
        route_count,
    )


def log_data_fetch_result(
    logger: logging.Logger,
    operation: str,
    success: bool,
    item_count: int | None = None,
    error: Exception | None = None,
) -> None:
    """Log data fetch result with consistent format."""
    if success:
        if item_count is not None:
            logger.debug("%s successful: %d items retrieved", operation, item_count)
        else:
            logger.debug("%s successful", operation)
    else:
        error_msg = str(error) if error else "Unknown error"
        logger.error("%s failed: %s", operation, error_msg)


def log_cache_operation(
    logger: logging.Logger,
    operation: str,
    cache_type: str,
    success: bool,
    details: str | None = None,
) -> None:
    """Log cache operations with consistent format."""
    message = f"{cache_type} cache {operation}"
    if details:
        message += f": {details}"

    if success:
        logger.debug(message)
    else:
        logger.warning(message)


def log_coordinator_update(
    logger: logging.Logger,
    update_type: str,
    route_count: int | None = None,
    duration: float | None = None,
) -> None:
    """Log coordinator update with structured information."""
    message = f"Coordinator update: {update_type}"

    if route_count is not None:
        message += f" ({route_count} routes)"

    if duration is not None:
        message += f" completed in {duration:.3f}s"

    logger.debug(message)


def sanitize_for_logging(data: Any, max_length: int = 100) -> str:
    """Sanitize data for safe logging."""
    if data is None:
        return "None"

    # Convert to string and truncate if needed
    data_str = str(data)
    if len(data_str) > max_length:
        return f"{data_str[:max_length]}..."

    return data_str
