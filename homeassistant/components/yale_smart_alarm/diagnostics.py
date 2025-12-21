"""Diagnostics support for Yale Smart Alarm."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import YaleConfigEntry

TO_REDACT = {
    "address",
    "name",
    "mac",
    "device_id",
    "user_id",
    "id",
    "mail_address",
    "report_account",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YaleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    assert coordinator.yale
    get_all_data = await hass.async_add_executor_job(coordinator.yale.get_all)
    return async_redact_data(asdict(get_all_data), TO_REDACT)
