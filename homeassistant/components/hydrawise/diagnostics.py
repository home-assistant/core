"""Diagnostics support for Hydrawise."""

from typing import Any

from pydrawise.diagnostics import redacted_dump

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import HydrawiseConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HydrawiseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data

    # The user holds the controllers, and those hold their zones and sensors.
    # pydrawise redacts the account and controller identity in there.
    return {
        "config_entry_data": async_redact_data(entry.data, TO_REDACT),
        "user": redacted_dump(coordinators.main.data.user),
        "daily_water_summary": redacted_dump(
            coordinators.water_use.data.daily_water_summary
        ),
    }
