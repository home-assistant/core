"""Diagnostics support for Kiosker integration.

This module provides comprehensive diagnostic data collection for the Kiosker integration,
including device status, coordinator state, integration health, and service registration
status. Sensitive data like API tokens and device identifiers are automatically redacted
for privacy protection.

Usage:
- Access via Settings → Devices & Services → Kiosker → Download Diagnostics
- The resulting JSON file contains troubleshooting information safe to share
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import KioskerConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Comprehensive list of sensitive data fields to redact
TO_REDACT = {
    "api_token",
    "token",
    "password",
    "key",
    "secret",
    "auth",
    "unique_id",
    "device_id",
    "serial_number",
    "mac_address",
    "macaddress",
    "latitude",
    "longitude",
    "location",
    "address",
    "coordinates",
    "wifi_ssid",
    "network_name",
    "ssid",
    "username",
    "email",
}

# Device status fields to extract safely
DEVICE_STATUS_FIELDS = [
    "model",
    "os_version",
    "app_name",
    "app_version",
    "battery_level",
    "battery_state",
    "last_interaction",
    "last_motion",
    "last_update",
    "ambient_light",
]

# Kiosker service names for service registration check
KIOSKER_SERVICES = [
    "navigate_url",
    "navigate_refresh",
    "navigate_home",
    "navigate_backward",
    "navigate_forward",
    "print",
    "clear_cookies",
    "clear_cache",
    "screensaver_interact",
    "blackout_set",
    "blackout_clear",
]


def _safe_get_device_info(coordinator_data: dict[str, Any]) -> dict[str, Any]:
    """Safely extract device information from coordinator data."""
    device_info = {}

    try:
        if coordinator_data.get("status"):
            status = coordinator_data["status"]

            # Use dictionary comprehension for cleaner field extraction
            device_info = {
                field: getattr(status, field, None) for field in DEVICE_STATUS_FIELDS
            }

    except (AttributeError, KeyError, TypeError) as err:
        _LOGGER.warning("Failed to extract device info for diagnostics: %s", err)
        device_info = {"extraction_error": f"Failed to extract device info: {err}"}

    return device_info


def _safe_get_coordinator_data(coordinator) -> dict[str, Any]:
    """Safely extract coordinator data with error handling."""
    try:
        return coordinator.data or {}
    except (AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to access coordinator data: %s", err)
        return {"access_error": f"Failed to access coordinator data: {err}"}


def _get_coordinator_metadata(coordinator) -> dict[str, Any]:
    """Extract coordinator metadata safely."""
    try:
        # Sanitize exception message to avoid sensitive data leakage
        last_exception = None
        if coordinator.last_exception:
            exception_msg = str(coordinator.last_exception)
            # Remove potential sensitive info from exception messages
            if any(
                sensitive in exception_msg.lower()
                for sensitive in ("token", "password", "key")
            ):
                last_exception = "Authentication or credential error (details hidden)"
            else:
                last_exception = exception_msg

        return {
            "last_update_success": coordinator.last_update_success,
            "last_exception": last_exception,
            "update_interval_seconds": coordinator.update_interval.total_seconds(),
            "name": coordinator.name,
            "last_update_success_time": getattr(
                coordinator, "last_update_success_time", None
            ),
        }
    except (AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to extract coordinator metadata: %s", err)
        return {"metadata_error": f"Failed to extract metadata: {err}"}


def _get_integration_info(entry: KioskerConfigEntry) -> dict[str, Any]:
    """Get integration state and setup information."""
    try:
        return {
            "version": getattr(entry, "version", 1),
            "minor_version": getattr(entry, "minor_version", 1),
            "state": entry.state.value if entry.state else "unknown",
            "title": entry.title,
            "domain": entry.domain,
            "setup_retry_count": getattr(entry, "_setup_retry_count", 0),
            "supports_unload": entry.supports_unload,
            "supports_remove_device": entry.supports_remove_device,
        }
    except (AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to extract integration info: %s", err)
        return {"integration_error": f"Failed to extract integration info: {err}"}


def _get_service_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get service registration status."""
    try:
        services_registered = []
        services_missing = []

        for service in KIOSKER_SERVICES:
            if hass.services.has_service(DOMAIN, service):
                services_registered.append(service)
            else:
                services_missing.append(service)

        return {
            "services_registered": services_registered,
            "services_missing": services_missing,
            "total_services_expected": len(KIOSKER_SERVICES),
            "registration_complete": len(services_missing) == 0,
        }
    except (AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to extract service info: %s", err)
        return {"service_error": f"Failed to extract service info: {err}"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KioskerConfigEntry
) -> dict[str, Any]:
    """Return comprehensive diagnostics for a Kiosker config entry.

    Collects device status, coordinator state, integration health, service
    registration status, and configuration details while protecting sensitive
    data through automatic redaction.

    Args:
        hass: Home Assistant instance
        entry: Kiosker configuration entry

    Returns:
        Dictionary containing diagnostic data with sensitive fields redacted
    """
    try:
        coordinator = entry.runtime_data
    except (AttributeError, TypeError) as err:
        _LOGGER.error("Failed to access runtime data for diagnostics: %s", err)
        return {
            "error": "Failed to access integration runtime data",
            "entry_basic_info": {
                "title": entry.title,
                "domain": entry.domain,
                "state": entry.state.value if entry.state else "unknown",
            },
        }

    # Safely collect all diagnostic data
    coordinator_data = _safe_get_coordinator_data(coordinator)
    device_info = _safe_get_device_info(coordinator_data)
    coordinator_metadata = _get_coordinator_metadata(coordinator)
    integration_info = _get_integration_info(entry)
    service_info = _get_service_info(hass)

    # Build comprehensive diagnostics dictionary

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "integration_info": integration_info,
        "coordinator_data": async_redact_data(coordinator_data, TO_REDACT),
        "coordinator_metadata": coordinator_metadata,
        "device_info": async_redact_data(device_info, TO_REDACT),
        "service_info": service_info,
        "api_info": {
            "host": entry.data.get("host", "unknown"),
            "port": entry.data.get("port", "unknown"),
            "ssl_enabled": entry.data.get("ssl", False),
            "ssl_verify": entry.data.get("ssl_verify", False),
        },
        "diagnostic_info": {
            "collected_at": "Data collected successfully",
            "redacted_fields": sorted(TO_REDACT),
            "data_collection_errors": "Check individual sections for error details",
        },
    }
