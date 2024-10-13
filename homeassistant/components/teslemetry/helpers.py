"""Teslemetry helper functions."""

import asyncio
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER, TeslemetryState


async def wake_up_vehicle(vehicle) -> None:
    """Wake up a vehicle."""
    async with vehicle.wakelock:
        times = 0
        while vehicle.coordinator.data["state"] != TeslemetryState.ONLINE:
            try:
                if times == 0:
                    cmd = await vehicle.api.wake_up()
                else:
                    cmd = await vehicle.api.vehicle()
                state = cmd["response"]["state"]
            except TeslaFleetError as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="wake_up_failed",
                    translation_placeholders={"message": e.message},
                ) from e
            vehicle.coordinator.data["state"] = state
            if state != TeslemetryState.ONLINE:
                times += 1
                if times >= 4:  # Give up after 30 seconds total
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="wake_up_timeout",
                    )
                await asyncio.sleep(times * 5)


async def handle_command(command) -> dict[str, Any]:
    """Handle a command."""
    try:
        result = await command
    except TeslaFleetError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_exception",
            translation_placeholders={"message": e.message},
        ) from e
    LOGGER.debug("Command result: %s", result)
    return result


async def handle_vehicle_command(command) -> Any:
    """Handle a vehicle command."""
    result = await handle_command(command)
    if (response := result.get("response")) is None:
        if error := result.get("error"):
            # No response with error
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": error},
            )
        # No response without error (unexpected)
        raise HomeAssistantError(f"Unknown response: {response}")
    if (result := response.get("result")) is not True:
        if reason := response.get("reason"):
            if reason in ("already_set", "not_charging", "requested"):
                # Reason is acceptable
                return result
            # Result of false with reason
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_reason",
                translation_placeholders={"reason": reason},
            )
        # Result of false without reason (unexpected)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_no_result"
        )
    # Response with result of true
    return result
