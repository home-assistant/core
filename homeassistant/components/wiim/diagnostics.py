"""Diagnostics support for WiiM."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import DATA_WIIM, WiimConfigEntry

TO_REDACT = {
    "configuration_url",
    "ip_address",
    "leader_udn",
    "mac",
    "mac_address",
    "member_udns",
    "name",
    "serial",
    "serial_number",
    "title",
    "udn",
    "uuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WiimConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data
    wiim_data = hass.data[DATA_WIIM]

    return {
        "device": async_redact_data(asdict(device.as_diagnostics()), TO_REDACT),
        "multiroom": async_redact_data(
            asdict(wiim_data.controller.get_group_snapshot(device.udn)), TO_REDACT
        ),
    }
