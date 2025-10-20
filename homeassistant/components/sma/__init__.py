"""The SMA integration."""

from __future__ import annotations

import logging

from pysma import SMA

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_GROUP, DOMAIN, PYSMA_OBJECT, PYSMA_REMOVE_LISTENER
from .coordinator import SMADataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


type SMAConfigEntry = ConfigEntry[SMADataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SMAConfigEntry) -> bool:
    """Set up sma from a config entry."""

    protocol = "https" if entry.data[CONF_SSL] else "http"
    url = f"{protocol}://{entry.data[CONF_HOST]}"

    sma = SMA(
        session=async_get_clientsession(
            hass=hass, verify_ssl=entry.data[CONF_VERIFY_SSL]
        ),
        url=url,
        password=entry.data[CONF_PASSWORD],
        group=entry.data[CONF_GROUP],
    )

    coordinator = SMADataUpdateCoordinator(hass, entry, sma)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Ensure the SMA session closes when Home Assistant stops
    async def _async_handle_shutdown(event: Event) -> None:
        await coordinator.async_close_sma_session()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_handle_shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[PYSMA_OBJECT].close_session()
        data[PYSMA_REMOVE_LISTENER]()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entry."""

    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        if entry.minor_version == 1:
            minor_version = 2
            hass.config_entries.async_update_entry(
                entry, unique_id=str(entry.unique_id), minor_version=minor_version
            )

    _LOGGER.debug("Migration successful")

    return True
