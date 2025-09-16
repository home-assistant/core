"""The HERE Travel Time integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_API_KEY, CONF_MODE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import CONF_TRAFFIC_MODE, TRAVEL_MODE_PUBLIC
from .coordinator import (
    HereConfigEntry,
    HERERoutingDataUpdateCoordinator,
    HERETransitDataUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: HereConfigEntry) -> bool:
    """Set up HERE Travel Time from a config entry."""
    api_key = config_entry.data[CONF_API_KEY]

    cls: type[HERETransitDataUpdateCoordinator | HERERoutingDataUpdateCoordinator]
    if config_entry.data[CONF_MODE] in {TRAVEL_MODE_PUBLIC, "publicTransportTimeTable"}:
        cls = HERETransitDataUpdateCoordinator
    else:
        cls = HERERoutingDataUpdateCoordinator

    data_coordinator = cls(hass, config_entry, api_key)
    config_entry.runtime_data = data_coordinator

    async def _async_update_at_start(_: HomeAssistant) -> None:
        await data_coordinator.async_refresh()

    config_entry.async_on_unload(async_at_started(hass, _async_update_at_start))
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: HereConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: HereConfigEntry
) -> bool:
    """Migrate an old config entry."""

    if config_entry.version == 1 and config_entry.minor_version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )
        options = dict(config_entry.options)
        options[CONF_TRAFFIC_MODE] = True

        hass.config_entries.async_update_entry(
            config_entry, options=options, version=1, minor_version=2
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )
    return True
