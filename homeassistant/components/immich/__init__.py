"""The Immich integration."""

from __future__ import annotations

from aioimmich import Immich
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import ImmichConfigEntry, ImmichDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up immich integration."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Set up Immich from a config entry."""

    session = async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL])
    immich = Immich(
        session,
        entry.data[CONF_API_KEY],
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
        "home-assistant",
    )

    try:
        user_info = await immich.users.async_get_my_user()
    except ImmichUnauthorizedError as err:
        raise ConfigEntryAuthFailed from err
    except CONNECT_ERRORS as err:
        raise ConfigEntryNotReady from err

    coordinator = ImmichDataUpdateCoordinator(hass, entry, immich, user_info.is_admin)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
