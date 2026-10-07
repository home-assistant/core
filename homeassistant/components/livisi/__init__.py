"""The Livisi Smart Home integration."""

from typing import Final

from livisi import LivisiException, WrongCredentialException

from homeassistant import core
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: core.HomeAssistant, entry: LivisiConfigEntry) -> bool:
    """Set up Livisi Smart Home from a config entry."""
    coordinator = LivisiDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_setup()
    except WrongCredentialException as exception:
        raise ConfigEntryAuthFailed from exception
    except LivisiException as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_close)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Livisi",
        name=f"SHC {coordinator.controller_type} {coordinator.serial_number}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    entry.async_create_background_task(
        hass, coordinator.ws_connect(), "livisi-ws_connect"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LivisiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
