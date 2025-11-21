"""Diagnostics platform for the Xbox integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import XboxConfigEntry

TO_REDACT = {
    "bio",
    "display_name",
    "display_pic_raw",
    "gamertag",
    "linked_accounts",
    "location",
    "modern_gamertag_suffix",
    "modern_gamertag",
    "real_name",
    "unique_modern_gamertag",
    "xuid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: XboxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = config_entry.runtime_data.status
    consoles_coordinator = config_entry.runtime_data.consoles

    presence = [
        async_redact_data(person.model_dump(), TO_REDACT)
        for person in coordinator.data.presence.values()
    ]
    consoles_status = [
        {
            "status": console.status.model_dump(),
            "app_details": (
                console.app_details.model_dump() if console.app_details else None
            ),
        }
        for console in coordinator.data.consoles.values()
    ]
    consoles_list = consoles_coordinator.data.model_dump()
    title_info = [title.model_dump() for title in coordinator.data.title_info.values()]

    return {
        "consoles_status": consoles_status,
        "consoles_list": consoles_list,
        "presence": presence,
        "title_info": title_info,
    }
