"""Teslemetry helper functions."""

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

from tesla_fleet_api.exceptions import InsufficientCredits, TeslaFleetError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import CREDITS_URL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import TeslemetryConfigEntry

INSUFFICIENT_CREDITS_ISSUE = "insufficient_credits"

# A credits event clears the insufficient credits issue when the account has
# quota credits still available, or a balance topup has been applied.
CREDITS_QUOTA_FRACTION_THRESHOLD = 0.95
CREDITS_BALANCE_THRESHOLD = 25


def insufficient_credits_issue_id(entry: TeslemetryConfigEntry) -> str:
    """Return the per-config-entry insufficient credits issue id.

    The issue is scoped to the config entry so that one account running out of
    credits does not clear (or get cleared by) another account's repair.
    """
    return f"{INSUFFICIENT_CREDITS_ISSUE}_{entry.entry_id}"


def flatten(
    data: dict[str, Any],
    parent: str | None = None,
    *,
    skip_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Flatten the data structure."""
    result = {}
    for key, value in data.items():
        skip = skip_keys and key in skip_keys
        if parent:
            key = f"{parent}_{key}"
        if isinstance(value, dict) and not skip:
            result.update(flatten(value, key, skip_keys=skip_keys))
        else:
            result[key] = value
    return result


async def handle_command(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    command: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    """Handle a command."""
    issue_id = insufficient_credits_issue_id(entry)
    try:
        result = await command
    except InsufficientCredits as e:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=INSUFFICIENT_CREDITS_ISSUE,
            translation_placeholders={"credits_url": CREDITS_URL},
            learn_more_url=CREDITS_URL,
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=INSUFFICIENT_CREDITS_ISSUE,
        ) from e
    except TeslaFleetError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_exception",
            translation_placeholders={"message": e.message},
        ) from e
    # A successful command means the account has credits again
    ir.async_delete_issue(hass, DOMAIN, issue_id)
    LOGGER.debug("Command result: %s", result)
    return result


async def handle_vehicle_command(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    command: Awaitable[dict[str, Any]],
) -> Any:
    """Handle a vehicle command."""
    result = await handle_command(hass, entry, command)
    if (response := result.get("response")) is None:
        if error := result.get("error"):
            # No response with error
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"error": error},
            )
        # No response without error (unexpected)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_no_response"
        )
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


@callback
def async_handle_credits(
    hass: HomeAssistant, entry: TeslemetryConfigEntry, credits: dict[str, Any]
) -> None:
    """Clear the insufficient credits issue when credits become available."""
    quota = credits.get("quota")
    fraction = quota.get("fraction") if isinstance(quota, dict) else None
    quota_available = (
        isinstance(fraction, (int, float))
        and not isinstance(fraction, bool)
        and fraction < CREDITS_QUOTA_FRACTION_THRESHOLD
    )
    if quota_available or credits.get("balance", 0) > CREDITS_BALANCE_THRESHOLD:
        ir.async_delete_issue(hass, DOMAIN, insufficient_credits_issue_id(entry))


@callback
def async_update_device_sw_version(
    hass: HomeAssistant, identifier: str, sw_version: str
) -> None:
    """Update the software version in the device registry."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device(identifiers={(DOMAIN, identifier)}):
        if device.sw_version != sw_version:
            dev_reg.async_update_device(device.id, sw_version=sw_version)
