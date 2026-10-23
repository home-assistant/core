"""Diagnostics support for the Mijn Farmad Apotheek integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from . import FarmadConfigEntry
from .const import CONF_REFRESH_TOKEN

TO_REDACT = {CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, "title", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FarmadConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
    if (data := getattr(entry, "runtime_data", None)) is not None:
        diagnostics["products"] = {
            apb: len(products) for apb, products in data.products.items()
        }
    return diagnostics
