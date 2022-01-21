"""Diagnostics support for UniFi Network."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.system_info import async_get_system_info

from .const import DOMAIN as UNIFI_DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {}

    diag["home_assistant"] = await async_get_system_info(hass)
    diag["config_entry"] = dict(config_entry.data)
    diag["site_role"] = controller.site_role
    diag["entities"] = controller.entities

    diag["clients"] = {k: v.raw for k, v in controller.api.clients.items()}
    diag["devices"] = {k: v.raw for k, v in controller.api.devices.items()}
    diag["dpi_apps"] = {k: v.raw for k, v in controller.api.dpi_apps.items()}
    diag["dpi_groups"] = {k: v.raw for k, v in controller.api.dpi_groups.items()}
    diag["wlans"] = {k: v.raw for k, v in controller.api.wlans.items()}

    return diag
