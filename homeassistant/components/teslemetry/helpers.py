"""Teslemetry helper functions."""

from collections.abc import Awaitable
import os
from pathlib import Path
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.teslemetry import Teslemetry

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR

from .const import DOMAIN, LEGACY_POWERWALL_KEY_FILE, LOGGER, POWERWALL_KEY_FILE


def rsa_key_path(hass: HomeAssistant) -> str:
    """Return the path of the shared RSA private key file in the storage dir."""
    return hass.config.path(STORAGE_DIR, POWERWALL_KEY_FILE)


def _migrate_legacy_rsa_key(legacy_path: str, path: str) -> None:
    """Move a pre-existing key from the config root into the storage dir.

    The gateway's retained authorization is bound to this key, so an install
    that already paired against the legacy path must keep the same key rather
    than have a fresh one generated over it.
    """
    if os.path.isfile(legacy_path) and not os.path.isfile(path):
        os.replace(legacy_path, path)


async def async_load_rsa_keyholder(hass: HomeAssistant) -> tuple[Teslemetry, bytes]:
    """Return the shared RSA keyholder and its PEM, migrating/generating as needed.

    Both the subentry pairing flow and runtime routing resolve the key through
    this single helper so they always sign with the same key material.
    """
    path = rsa_key_path(hass)
    legacy_path = hass.config.path(LEGACY_POWERWALL_KEY_FILE)
    await hass.async_add_executor_job(_migrate_legacy_rsa_key, legacy_path, path)
    keyholder = Teslemetry(session=async_get_clientsession(hass), access_token="")
    await keyholder.get_rsa_private_key(path)
    pem = await hass.async_add_executor_job(Path(path).read_bytes)
    return keyholder, pem


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
    hass: HomeAssistant, identifier: str, config_entry_id: str, sw_version: str
) -> None:
    """Update the software version in the device registry."""
    dev_reg = dr.async_get(hass)
    if device := dev_reg.async_get_device_by_identifier(
        (DOMAIN, identifier), config_entry_id
    ):
        if device.sw_version != sw_version:
            dev_reg.async_update_device(device.id, sw_version=sw_version)
