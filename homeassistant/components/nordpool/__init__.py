"""The Nord Pool component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
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


async def async_setup_entry(hass: HomeAssistant, entry: NordPoolConfigEntry) -> bool:
    """Set up Nord Pool from a config entry."""

    await cleanup_device(hass, entry)

    coordinator = NordPoolDataUpdateCoordinator(hass, entry)
    await coordinator.fetch_data(dt_util.utcnow())
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="initial_update_failed",
            translation_placeholders={"error": str(coordinator.last_exception)},
        )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NordPoolConfigEntry) -> bool:
    """Unload Nord Pool config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def cleanup_device(hass: HomeAssistant, entry: NordPoolConfigEntry) -> None:
    """Cleanup device and entities."""
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    entries = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
    for area in entry.data[CONF_AREAS]:
        for _entry in entries:
            if _entry.identifiers == {(DOMAIN, area)}:
                continue

            LOGGER.debug("Removing device %s", _entry.name)
            entities = er.async_entries_for_device(entity_reg, _entry.id)
            for _entity in entities:
                entity_reg.async_remove(_entity.entity_id)
            device_reg.async_clear_config_entry(entry.entry_id)
