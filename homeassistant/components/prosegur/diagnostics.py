"""Diagnostics support for Prosegur."""

from __future__ import annotations

from typing import Any

from pyprosegur.installation import Installation

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import ProsegurConfigEntry
from .const import CONF_CONTRACT

TO_REDACT = {"description", "latitude", "longitude", "contractId", "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ProsegurConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    installation = await Installation.retrieve(
        entry.runtime_data, entry.data[CONF_CONTRACT]
    )

    activity = await installation.activity(entry.runtime_data)

    return {
        "installation": async_redact_data(installation.data, TO_REDACT),
        "activity": activity,
    }
