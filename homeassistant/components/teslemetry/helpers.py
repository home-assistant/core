"""Teslemetry helper functions."""

from collections.abc import Awaitable
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, LOGGER


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


async def handle_command(command: Awaitable[dict[str, Any]]) -> dict[str, Any]:
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


async def handle_vehicle_command(command: Awaitable[dict[str, Any]]) -> Any:
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


async def async_set_charge_on_solar(
    api: Vehicle,
    *,
    enabled: bool,
    lower_charge_limit: int,
    charge_limit_soc: int | None,
) -> int:
    """Send a charge-on-solar command, omitting the upper bound if it isn't known yet.

    Returns the lower limit actually sent, clamped to the upper bound if it is known.
    """
    upper_charge_limit: int | None = None
    if charge_limit_soc is not None:
        upper_charge_limit = max(30, min(charge_limit_soc, 100))
        lower_charge_limit = min(lower_charge_limit, upper_charge_limit)
    await handle_vehicle_command(
        api.charge_on_solar(
            enabled=enabled,
            lower_charge_limit=lower_charge_limit,
            upper_charge_limit=upper_charge_limit,
        )
    )
    return lower_charge_limit


@callback
def async_remove_stale_vehicle_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    domain: str,
    vins: set[str],
    valid_unique_ids: set[str],
) -> None:
    """Remove registry entries for vehicle entities that are no longer created."""
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, config_entry_id):
        if (
            entity.domain == domain
            and entity.unique_id not in valid_unique_ids
            and any(entity.unique_id.startswith(f"{vin}-") for vin in vins)
        ):
            entity_registry.async_remove(entity.entity_id)


@callback
def async_update_device_sw_version(
    hass: HomeAssistant, identifier: str, config_entry_id: str, sw_version: str
) -> None:
    """Update the software version in the device registry."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device_by_identifier(
        (DOMAIN, identifier), config_entry_id
    ):
        if device.sw_version != sw_version:
            dev_reg.async_update_device(device.id, sw_version=sw_version)
