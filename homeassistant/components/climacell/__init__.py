"""The ClimaCell integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.tomorrowio import DOMAIN as TOMORROW_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_VERSION
from homeassistant.core import HomeAssistant

from .const import CONF_TIMESTEP, DEFAULT_TIMESTEP, DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ClimaCell API from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    params: dict[str, Any] = {}
    # If config entry options not set up, set them up
    if not entry.options:
        params["options"] = {
            CONF_TIMESTEP: DEFAULT_TIMESTEP,
        }
    else:
        # Use valid timestep if it's invalid
        timestep = entry.options[CONF_TIMESTEP]
        if timestep not in (1, 5, 15, 30):
            if timestep <= 2:
                timestep = 1
            elif timestep <= 7:
                timestep = 5
            elif timestep <= 20:
                timestep = 15
            else:
                timestep = 30
            new_options = entry.options.copy()
            new_options[CONF_TIMESTEP] = timestep
            params["options"] = new_options
    # Add API version if not found
    if CONF_API_VERSION not in entry.data:
        new_data = entry.data.copy()
        new_data[CONF_API_VERSION] = 3
        params["data"] = new_data

    if params:
        hass.config_entries.async_update_entry(entry, **params)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            TOMORROW_DOMAIN,
            context={"source": SOURCE_IMPORT, "old_config_entry_id": entry.entry_id},
            data=entry.data,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    return True
