"""The Forecast.Solar integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_MODULES_POWER,
)
from .coordinator import ForecastSolarConfigEntry, ForecastSolarDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_migrate_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Migrate old config entry."""

    if entry.version == 1:
        new_options = entry.options.copy()
        new_options |= {
            CONF_MODULES_POWER: new_options.pop("modules power"),
            CONF_DAMPING_MORNING: new_options.get(CONF_DAMPING, 0.0),
            CONF_DAMPING_EVENING: new_options.pop(CONF_DAMPING, 0.0),
        }

        hass.config_entries.async_update_entry(
            entry, data=entry.data, options=new_options, version=2
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Set up Forecast.Solar from a config entry."""
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
