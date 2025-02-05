"""Component to control TOLO Sauna/Steam Bath."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESSORIES, CONF_EXPERT, DOMAIN
from .coordinator import ToloSaunaUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tolo from a config entry."""
    coordinator = ToloSaunaUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate TOLO config entry."""
    config_data = dict(config_entry.data)

    if config_entry.minor_version < 2:
        if config_data.get(CONF_ACCESSORIES) is None:
            config_data[CONF_ACCESSORIES] = {}
        if config_data.get(CONF_EXPERT) is None:
            config_data[CONF_EXPERT] = {}
    hass.config_entries.async_update_entry(
        config_entry, data=config_data, minor_version=2, version=1
    )

    return True
