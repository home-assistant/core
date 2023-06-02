"""The EnergyZero integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_ENERGY_MODIFYER, CONF_GAS_MODIFYER, DEFAULT_MODIFYER, DOMAIN
from .coordinator import EnergyZeroDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EnergyZero from a config entry."""

    gas_modifyer = (
        entry.options[CONF_GAS_MODIFYER]
        if CONF_GAS_MODIFYER in entry.options
        else DEFAULT_MODIFYER
    )
    energy_modifyer = (
        entry.options[CONF_ENERGY_MODIFYER]
        if CONF_ENERGY_MODIFYER in entry.options
        else DEFAULT_MODIFYER
    )

    coordinator = EnergyZeroDataUpdateCoordinator(hass, gas_modifyer, energy_modifyer)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.energyzero.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EnergyZero config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
