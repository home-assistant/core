"""The Roth Touchline SL integration."""

from __future__ import annotations

from pytouchlinesl import TouchlineSL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TouchlineSLModuleCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type TouchlineSLConfigEntry = ConfigEntry[dict[str, TouchlineSLModuleCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineSLConfigEntry) -> bool:
    """Set up Roth Touchline SL from a config entry."""
    account = TouchlineSL(
        username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )

    coordinators: dict[str, TouchlineSLModuleCoordinator] = {}
    modules = await account.modules()

    device_registry = dr.async_get(hass)
    for module in modules:
        coordinator = TouchlineSLModuleCoordinator(hass, module=module)
        coordinators[module.id] = coordinator
        await coordinator.async_config_entry_first_refresh()

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.data.module.id)},
            name=coordinator.data.module.name,
            manufacturer="Roth",
            model=coordinator.data.module.type,
            sw_version=coordinator.data.module.version,
        )

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TouchlineSLConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
