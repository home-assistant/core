"""Support for the Autarco diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AutarcoConfigEntry, AutarcoDataUpdateCoordinator

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AutarcoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    autarco_data: list[AutarcoDataUpdateCoordinator] = config_entry.runtime_data

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "sites_data": [
            {
                "id": coordinator.site.site_id,
                "name": coordinator.site.system_name,
                "health": coordinator.site.health,
                "solar": {
                    "power_production": coordinator.data.solar.power_production,
                    "energy_production_today": coordinator.data.solar.energy_production_today,
                    "energy_production_month": coordinator.data.solar.energy_production_month,
                    "energy_production_total": coordinator.data.solar.energy_production_total,
                },
            }
            for coordinator in autarco_data
        ],
    }
