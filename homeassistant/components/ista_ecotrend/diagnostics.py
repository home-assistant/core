"""Diagnostics platform for ista EcoTrend integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import IstaConfigEntry

TO_REDACT = {
    "firstName",
    "lastName",
    "street",
    "houseNumber",
    "documentNumber",
    "postalCode",
    "city",
    "propertyNumber",
    "idAtCustomerUser",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: IstaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "details": async_redact_data(config_entry.runtime_data.details, TO_REDACT),
        "data": async_redact_data(config_entry.runtime_data.data, TO_REDACT),
    }
