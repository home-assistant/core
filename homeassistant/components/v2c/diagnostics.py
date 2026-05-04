"""Diagnostics support for V2C."""

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import V2CConfigEntry

TO_REDACT = {CONF_HOST, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: V2CConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    if TYPE_CHECKING:
        assert coordinator.evse

    coordinator_data = coordinator.evse.data
    assert coordinator_data is not None
    evse_raw_data = coordinator.evse.raw_data

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": str(coordinator_data),
        "raw_data": asdict(coordinator_data),
        "host_status": evse_raw_data["status_code"],
    }
