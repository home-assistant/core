"""Diagnostics support for TwenteMilieu."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .const import CONF_HOUSE_LETTER, CONF_HOUSE_NUMBER, CONF_POST_CODE
from .coordinator import TwenteMilieuConfigEntry

TO_REDACT = {CONF_ID, CONF_POST_CODE, CONF_HOUSE_NUMBER, CONF_HOUSE_LETTER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": {
            f"WasteType.{waste_type.name}": [
                waste_date.isoformat() for waste_date in waste_dates
            ]
            for waste_type, waste_dates in entry.runtime_data.data.items()
        },
    }
