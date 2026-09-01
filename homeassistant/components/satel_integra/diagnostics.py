"""Diagnostics support for Satel Integra."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

from .const import CONF_ENCRYPTION_KEY
from .coordinator import SatelConfigEntry

TO_REDACT = {CONF_CODE, CONF_ENCRYPTION_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SatelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    panel_info = await entry.runtime_data.client.controller.read_panel_info()
    diag: dict[str, Any] = {}

    diag["config_entry_data"] = async_redact_data(entry.data, TO_REDACT)
    diag["config_entry_options"] = async_redact_data(entry.options, TO_REDACT)

    diag["subentries"] = dict(entry.subentries)
    diag["panel_info"] = asdict(panel_info)

    return diag
