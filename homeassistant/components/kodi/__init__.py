"""The Kodi integration."""

from pykodi import InvalidAuthError, Kodi, get_kodi_connection

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .connection import KodiConfigEntry, KodiConnectionManager
from .const import CONF_WS_PORT, DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KodiConfigEntry) -> None:
    """Set up Kodi from a config entry."""
    conn = get_kodi_connection(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_WS_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_SSL],
        session=async_get_clientsession(hass),
    )

    manager = KodiConnectionManager(hass, entry, conn, Kodi(conn))
    # Also runs when the setup fails or is cancelled
    entry.async_on_unload(manager.async_stop)
    # Listen before the setup waits for Kodi, so a stop during it closes the connection.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, manager.async_stop)
    )

    try:
        await manager.async_setup()
    except InvalidAuthError as error:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="login_failed",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from error

    entry.runtime_data = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    manager.async_start()


async def async_unload_entry(hass: HomeAssistant, entry: KodiConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
