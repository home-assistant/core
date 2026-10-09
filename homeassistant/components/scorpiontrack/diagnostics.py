"""Diagnostics support for ScorpionTrack."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import CONF_SHARE_TOKEN
from .coordinator import ScorpionTrackConfigEntry

TO_REDACT = {
    CONF_SHARE_TOKEN,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    "address",
    "id",
    "name",
    "owner_name",
    "registration",
    "title",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = asdict(coordinator.data)
    # The redactor traverses lists, but not tuples.
    data["vehicles"] = list(data["vehicles"])

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(data, TO_REDACT),
    }
