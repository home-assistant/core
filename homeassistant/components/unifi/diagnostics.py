"""Diagnostics support for UniFi Network."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_CONTROLLER, DOMAIN as UNIFI_DOMAIN

TO_REDACT = {CONF_CONTROLLER, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {}

    diag["config_entry"] = async_redact_data(config_entry.data, TO_REDACT)
    diag["site_role"] = controller.site_role
    diag["entities"] = controller.entities

    diag["clients"] = {k: v.raw for k, v in controller.api.clients.items()}
    diag["devices"] = {k: v.raw for k, v in controller.api.devices.items()}
    diag["dpi_apps"] = {k: v.raw for k, v in controller.api.dpi_apps.items()}
    diag["dpi_groups"] = {k: v.raw for k, v in controller.api.dpi_groups.items()}
    diag["wlans"] = {k: v.raw for k, v in controller.api.wlans.items()}

    return diag
