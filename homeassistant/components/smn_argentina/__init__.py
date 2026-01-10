"""The SMN Weather integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import ALERT_EVENT_MAP, ALERT_LEVEL_MAP, DOMAIN
from .coordinator import ArgentinaSMNDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.WEATHER]

# Service name
SERVICE_GET_ALERTS_FOR_LOCATION = "get_alerts_for_location"

# Service schema

SERVICE_GET_ALERTS_FOR_LOCATION_SCHEMA = vol.Schema(
    {
        vol.Required("location_id"): cv.string,
    }
)


def _get_alert_details(
    event_id: int, max_level: int, reports: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Get description and instruction for a specific alert event."""
    for report in reports:
        if report.get("event_id") == event_id:
            levels = report.get("levels", [])
            for level_data in levels:
                if level_data.get("level") == max_level:
                    return (
                        level_data.get("description"),
                        level_data.get("instruction"),
                    )
    return None, None


def _parse_alerts(alerts_data: dict[str, Any]) -> dict[str, Any]:
    """Parse raw alerts data into structured format for automations."""
    if not alerts_data or not isinstance(alerts_data, dict):
        return {"active_alerts": [], "max_severity": "info", "area_id": None}

    warnings = alerts_data.get("warnings", [])
    reports = alerts_data.get("reports", [])
    area_id = alerts_data.get("area_id")

    active_alerts = []
    max_severity_level = 1

    # Get current day's warnings
    if warnings and len(warnings) > 0:
        current_warning = warnings[0]
        events = current_warning.get("events", [])

        for event in events:
            event_id = event.get("id")
            max_level = event.get("max_level", 1)

            # Skip level 1 (no alert)
            if max_level <= 1:
                continue

            # Track max severity
            max_severity_level = max(max_severity_level, max_level)

            # Get event name
            event_name = ALERT_EVENT_MAP.get(event_id, f"unknown_{event_id}")

            # Get level info
            level_info = ALERT_LEVEL_MAP.get(max_level, ALERT_LEVEL_MAP[1])

            # Find report for this event
            description, instruction = _get_alert_details(event_id, max_level, reports)

            active_alerts.append(
                {
                    "event_id": event_id,
                    "event_name": event_name,
                    "max_level": max_level,
                    "level_name": level_info["name"],
                    "color": level_info["color"],
                    "severity": level_info["severity"],
                    "date": current_warning.get("date"),
                    "description": description,
                    "instruction": instruction,
                }
            )

    # Get overall max severity
    max_severity_info = ALERT_LEVEL_MAP.get(max_severity_level, ALERT_LEVEL_MAP[1])

    return {
        "active_alerts": active_alerts,
        "max_severity": max_severity_info["severity"],
        "max_level": max_severity_level,
        "area_id": area_id,
        "updated": alerts_data.get("updated"),
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator]
) -> bool:
    """Set up SMN from a config entry."""
    # Create coordinator
    coordinator = ArgentinaSMNDataUpdateCoordinator(hass, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    entry.runtime_data = coordinator

    # Register service (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_GET_ALERTS_FOR_LOCATION):

        async def handle_get_alerts_for_location(call: ServiceCall) -> dict[str, Any]:
            """Handle get_alerts_for_location service call."""
            location_id = call.data.get("location_id")

            # Get token manager from first available coordinator (via config entries)
            smn_entries = hass.config_entries.async_entries(DOMAIN)
            if not smn_entries:
                raise HomeAssistantError(
                    "No SMN integration configured. Set up integration first."
                )

            # Get first coordinator to access API client
            coordinator = smn_entries[0].runtime_data

            # Fetch alerts using API client
            try:
                _LOGGER.debug("Fetching alerts for location ID: %s", location_id)
                # Access private members to use the existing API client session
                data = await coordinator._smn_data._api_client.async_get_alerts(  # noqa: SLF001
                    location_id
                )

                # Parse and return alerts
                result = _parse_alerts(data)
                _LOGGER.debug(
                    "Fetched alerts for location %s: %d active alerts with max severity '%s'",
                    location_id,
                    len(result.get("active_alerts", [])),
                    result.get("max_severity", "info"),
                )

            except Exception as err:
                _LOGGER.error(
                    "Error fetching alerts for location %s: %s", location_id, err
                )
                raise HomeAssistantError(f"Error fetching alerts: {err}") from err
            else:
                return result

        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_ALERTS_FOR_LOCATION,
            handle_get_alerts_for_location,
            schema=SERVICE_GET_ALERTS_FOR_LOCATION_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator]
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
