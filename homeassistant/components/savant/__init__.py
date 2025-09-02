"""The Savant Home Automation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import (
    SavantAudioSwitchCoordinator,
    SavantCoordinator,
    SavantVideoSwitchCoordinator,
)

_PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


type SavantConfigEntry = ConfigEntry[SavantCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SavantConfigEntry) -> bool:
    """Set up Savant Home Automation from a config entry."""
    match entry.data["type"]:
        case "Audio":
            coordinator: SavantCoordinator = SavantAudioSwitchCoordinator(hass, entry)
        case "Video":
            coordinator = SavantVideoSwitchCoordinator(hass, entry)
        case _:
            raise ConfigEntryError

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SavantConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_setup(hass: HomeAssistant, entry: SavantConfigEntry) -> bool:
    """Set up Savant Home Automation basic configuration."""
    return True
