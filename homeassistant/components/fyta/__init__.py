"""Initialization of FYTA integration."""

from __future__ import annotations

from datetime import datetime
import logging

from fyta_cli.fyta_connector import FytaConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.dt import async_get_time_zone

from .const import CONF_EXPIRATION
from .coordinator import FytaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
]
type FytaConfigEntry = ConfigEntry[FytaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FytaConfigEntry) -> bool:
    """Set up the Fyta integration."""
    tz: str = hass.config.time_zone

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    access_token: str = entry.data[CONF_ACCESS_TOKEN]
    expiration: datetime = datetime.fromisoformat(
        entry.data[CONF_EXPIRATION]
    ).astimezone(await async_get_time_zone(tz))

    fyta = FytaConnector(
        username, password, access_token, expiration, tz, async_get_clientsession(hass)
    )

    coordinator = FytaCoordinator(hass, fyta)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FytaConfigEntry) -> bool:
    """Unload Fyta entity."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: FytaConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            new = {**config_entry.data}
            fyta = FytaConnector(
                config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
            )
            credentials = await fyta.login()
            await fyta.client.close()

            new[CONF_ACCESS_TOKEN] = credentials.access_token
            new[CONF_EXPIRATION] = credentials.expiration.isoformat()

            hass.config_entries.async_update_entry(
                config_entry, data=new, minor_version=2, version=1
            )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
