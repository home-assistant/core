"""Teslemetry helper functions."""

import asyncio
from collections.abc import Awaitable
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.tesla.bluetooth import TeslaBluetooth

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import BLE_PARENT_KEY, BLE_PARENT_LOCK_KEY, DOMAIN, LOGGER, VEHICLE_KEY_FILE


async def async_get_ble_parent(hass: HomeAssistant) -> TeslaBluetooth:
    """Return a shared TeslaBluetooth parent with the private key loaded.

    Cached on ``hass.data`` and guarded by a lock so the key file is created
    and read exactly once even when vehicle setup and a pairing flow (or
    several) race to first-time init - two independent parents could otherwise
    both generate and overwrite the key.
    """
    parent: TeslaBluetooth | None = hass.data.get(BLE_PARENT_KEY)
    if parent is not None:
        return parent
    lock: asyncio.Lock = hass.data.setdefault(BLE_PARENT_LOCK_KEY, asyncio.Lock())
    async with lock:
        parent = hass.data.get(BLE_PARENT_KEY)
        if parent is None:
            parent = TeslaBluetooth()  # type: ignore[no-untyped-call]
            await parent.get_private_key(hass.config.path(VEHICLE_KEY_FILE))
            hass.data[BLE_PARENT_KEY] = parent
    return parent


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


@callback
def async_update_device_sw_version(
    hass: HomeAssistant, identifier: str, sw_version: str
) -> None:
    """Update the software version in the device registry."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device(identifiers={(DOMAIN, identifier)}):
        if device.sw_version != sw_version:
            dev_reg.async_update_device(device.id, sw_version=sw_version)
