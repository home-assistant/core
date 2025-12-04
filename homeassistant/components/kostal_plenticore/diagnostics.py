"""Diagnostics support for Kostal Plenticore."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import ATTR_IDENTIFIERS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import PlenticoreConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PlenticoreConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return diagnostics for a config entry."""
    data = {"config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT)}

    plenticore = config_entry.runtime_data

    # Get information from Kostal Plenticore library
    available_process_data = await plenticore.client.get_process_data()
    available_settings_data = await plenticore.client.get_settings()
    data["client"] = {
        "version": str(await plenticore.client.get_version()),
        "me": str(await plenticore.client.get_me()),
        "available_process_data": available_process_data,
        "available_settings_data": {
            module_id: [str(setting) for setting in settings]
            for module_id, settings in available_settings_data.items()
        },
    }

    # Add important information how the inverter is configured
    string_count_setting = await plenticore.client.get_setting_values(
        "devices:local", "Properties:StringCnt"
    )
    try:
        string_count = int(
            string_count_setting["devices:local"]["Properties:StringCnt"]
        )
    except ValueError:
        string_count = 0

    configuration_settings = await plenticore.client.get_setting_values(
        "devices:local",
        (
            "Properties:StringCnt",
            *(f"Properties:String{idx}Features" for idx in range(string_count)),
        ),
    )

    data["configuration"] = {
        **configuration_settings,
    }

    device_info = {**plenticore.device_info}
    device_info[ATTR_IDENTIFIERS] = REDACTED  # contains serial number
    data["device"] = device_info

    return data
