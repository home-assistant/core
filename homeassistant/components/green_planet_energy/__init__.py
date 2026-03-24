"""Green Planet Energy integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import GreenPlanetEnergyUpdateCoordinator
from .services import async_setup_services

type GreenPlanetEnergyConfigEntry = ConfigEntry[GreenPlanetEnergyUpdateCoordinator]

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Green Planet Energy component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GreenPlanetEnergyConfigEntry
) -> bool:
    """Set up Green Planet Energy from a config entry."""
    coordinator = GreenPlanetEnergyUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GreenPlanetEnergyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
