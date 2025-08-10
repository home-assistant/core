"""The EnergyZero integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import EnergyZeroConfigEntry, EnergyZeroDataUpdateCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up EnergyZero services."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: EnergyZeroConfigEntry) -> bool:
    """Set up EnergyZero from a config entry."""

    coordinator = EnergyZeroDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.energyzero.close()
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergyZeroConfigEntry) -> bool:
    """Unload EnergyZero config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
