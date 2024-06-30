"""The Mealie integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import MealieConfigEntry, MealieCoordinator
from .services import setup_services

PLATFORMS: list[Platform] = [Platform.CALENDAR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mealie component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Set up Mealie from a config entry."""

    coordinator = MealieCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MealieConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
