"""Litter-Robot services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry

SERVICE_SET_SLEEP_MODE = "set_sleep_mode"
SERVICE_START_RECORDING = "start_recording"
SERVICE_REASSIGN_VISIT = "reassign_visit"

START_RECORDING_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): cv.string,
        vol.Optional("serial"): cv.string,
    }
)

REASSIGN_VISIT_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Required("event_id"): cv.string,
        vol.Optional("from_pet_id"): cv.string,
        vol.Optional("to_pet_id"): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SLEEP_MODE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required("enabled"): cv.boolean,
            vol.Optional("start_time"): cv.time,
        },
        func="async_set_sleep_mode",
    )

    async def async_start_recording(call: ServiceCall) -> None:
        """Manually trigger a recording for a Litter-Robot 5 camera."""
        entry_id = call.data["config_entry_id"]
        serial_filter = call.data.get("serial")

        entry: LitterRobotConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if entry is None:
            raise ServiceValidationError(f"Config entry '{entry_id}' not found")

        coordinator = entry.runtime_data
        if coordinator.recording_manager is None:
            raise HomeAssistantError(
                "Recording is not enabled — turn it on via the integration options first"
            )

        from pylitterbot import LitterRobot5  # noqa: PLC0415

        triggered = 0
        for robot in coordinator.account.robots:
            if not isinstance(robot, LitterRobot5):
                continue
            if not robot.has_camera:
                continue
            if serial_filter and robot.serial != serial_filter:
                continue

            # Reset cooldown so the manual trigger always works
            coordinator.recording_manager._last_trigger_times.pop(robot.serial, None)
            coordinator.recording_manager.trigger_recording(
                robot, {"type": "MANUAL", "messageId": "manual"}
            )
            triggered += 1

        if triggered == 0:
            raise HomeAssistantError(
                "No LR5 cameras found"
                + (f" matching serial '{serial_filter}'" if serial_filter else "")
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_RECORDING,
        async_start_recording,
        schema=START_RECORDING_SCHEMA,
    )

    async def async_reassign_visit(call: ServiceCall) -> None:
        """Reassign or unassign a pet visit activity."""
        entry_id = call.data.get("config_entry_id")
        if entry_id is None:
            entries = hass.config_entries.async_entries(DOMAIN)
            if len(entries) != 1:
                raise ServiceValidationError(
                    "config_entry_id is required when multiple entries exist"
                )
            entry_id = entries[0].entry_id
        event_id = call.data["event_id"]
        from_pet_id = call.data.get("from_pet_id")
        to_pet_id = call.data.get("to_pet_id")

        if not from_pet_id and not to_pet_id:
            raise ServiceValidationError(
                "At least one of from_pet_id or to_pet_id must be provided"
            )

        entry: LitterRobotConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if entry is None:
            raise ServiceValidationError(f"Config entry '{entry_id}' not found")

        coordinator = entry.runtime_data

        from pylitterbot import LitterRobot5  # noqa: PLC0415

        # Find the activity in the cache to determine which robot it belongs to
        robot_serial = None
        for serial, activities in coordinator.camera_activities.items():
            for activity in activities:
                if activity.get("eventId") == event_id:
                    robot_serial = serial
                    break
            if robot_serial:
                break

        if not robot_serial:
            raise HomeAssistantError(
                f"Activity with eventId '{event_id}' not found in cache"
            )

        # Find the robot
        robot = None
        for r in coordinator.account.robots:
            if isinstance(r, LitterRobot5) and r.serial == robot_serial:
                robot = r
                break

        if robot is None:
            raise HomeAssistantError(
                f"Robot with serial '{robot_serial}' not found"
            )

        result = await robot.reassign_pet_visit(
            event_id=event_id,
            from_pet_id=from_pet_id,
            to_pet_id=to_pet_id,
        )

        if result is None:
            raise HomeAssistantError("Failed to reassign pet visit")

        # Update the activity in the local cache
        for i, activity in enumerate(coordinator.camera_activities[robot_serial]):
            if activity.get("eventId") == event_id:
                coordinator.camera_activities[robot_serial][i] = result
                break

        # Trigger a coordinator update to refresh sensors
        coordinator.async_set_updated_data(None)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REASSIGN_VISIT,
        async_reassign_visit,
        schema=REASSIGN_VISIT_SCHEMA,
    )
