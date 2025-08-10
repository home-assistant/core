"""The Nord Pool component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import CONF_AREAS, DOMAIN, LOGGER, PLATFORMS
from .coordinator import NordPoolDataUpdateCoordinator
from .services import async_setup_services

type NordPoolConfigEntry = ConfigEntry[NordPoolDataUpdateCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nord Pool service."""

    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: NordPoolConfigEntry
) -> bool:
    """Set up Nord Pool from a config entry."""

    await cleanup_device(hass, config_entry)

    coordinator = NordPoolDataUpdateCoordinator(hass, config_entry)
    await coordinator.fetch_data(dt_util.utcnow())
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="initial_update_failed",
            translation_placeholders={"error": str(coordinator.last_exception)},
        )
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: NordPoolConfigEntry
) -> bool:
    """Unload Nord Pool config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def cleanup_device(
    hass: HomeAssistant, config_entry: NordPoolConfigEntry
) -> None:
    """Cleanup device and entities."""
    device_reg = dr.async_get(hass)

    entries = dr.async_entries_for_config_entry(device_reg, config_entry.entry_id)
    for area in config_entry.data[CONF_AREAS]:
        for entry in entries:
            if entry.identifiers == {(DOMAIN, area)}:
                continue

            LOGGER.debug("Removing device %s", entry.name)
            device_reg.async_update_device(
                entry.id, remove_config_entry_id=config_entry.entry_id
            )
