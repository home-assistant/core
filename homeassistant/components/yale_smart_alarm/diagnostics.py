"""Diagnostics support for Yale Smart Alarm."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN
from .coordinator import YaleDataUpdateCoordinator

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
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    assert coordinator.yale
    get_all_data = await hass.async_add_executor_job(coordinator.yale.get_all)
    return async_redact_data(get_all_data, TO_REDACT)
