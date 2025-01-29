"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

import contextlib
from typing import Any

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry


async def _generate_appliance_diagnostics(
    client: HomeConnectClient, appliance: HomeConnectApplianceData
) -> dict[str, Any]:
    program_keys = None
    with contextlib.suppress(HomeConnectError):
        # Using get_available_programs serializes the response, and any
        # programs not in the enum are set to Program.UNKNOWN.
        # That's why here  we fetch the programs with a raw response so we can
        # get the actual program keys and the user can suggest the addition
        # of the missing programs to the enum to the aiohomeconnect library.
        program_response = await client._auth.request(  # noqa: SLF001
            "GET",
            f"/homeappliances/{appliance.info.ha_id}/programs/available",
        )
        if not program_response.is_error:
            program_keys = [
                program["key"]
                for program in program_response.json()["data"]["programs"]
            ]
    return {
        **appliance.info.to_dict(),
        "status": {key.value: status.value for key, status in appliance.status.items()},
        "settings": {
            key.value: setting.value for key, setting in appliance.settings.items()
        },
        "programs": program_keys,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        appliance.info.ha_id: await _generate_appliance_diagnostics(
            entry.runtime_data.client, appliance
        )
        for appliance in entry.runtime_data.data.values()
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    ha_id = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
    )
    return await _generate_appliance_diagnostics(
        entry.runtime_data.client, entry.runtime_data.data[ha_id]
    )
