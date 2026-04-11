"""The Kodi integration."""

from dataclasses import dataclass
import logging

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError, InvalidAuthError, Kodi, get_kodi_connection
from pykodi.kodi import KodiHTTPConnection, KodiWSConnection

from homeassistant.config_entries import ConfigEntry
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_WS_PORT, DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.BINARY_SENSOR]

type KodiConfigEntry = ConfigEntry[KodiRuntimeData]


@dataclass
class KodiRuntimeData:
    """Data class to hold Kodi runtime data."""

    connection: KodiHTTPConnection | KodiWSConnection
    kodi: Kodi
    screensaver_active: bool | None = None

    def set_screensaver_state(self, screensaver_active: bool | None) -> bool:
        """Set the current screensaver state."""
        changed = self.screensaver_active != screensaver_active
        self.screensaver_active = screensaver_active
        return changed

    async def async_update_screensaver_state(self) -> bool:
        """Refresh the Kodi screensaver state."""
        if not self.connection.connected:
            return self.set_screensaver_state(None)

        try:
            display_status = await self.kodi.call_method(
                "XBMC.GetInfoBooleans",
                booleans=["System.ScreenSaverActive"],
            )
        except (ProtocolError, TransportError):
            return self.set_screensaver_state(None)

        return self.set_screensaver_state(
            display_status.get("System.ScreenSaverActive")
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KodiConfigEntry) -> bool:
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

    kodi = Kodi(conn)

    try:
        await conn.connect()
    except CannotConnectError:
        pass
    except InvalidAuthError as error:
        _LOGGER.error(
            "Login to %s failed: [%s]",
            entry.data[CONF_HOST],
            error,
        )
        return False

    async def _close(event):
        await conn.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    entry.runtime_data = KodiRuntimeData(connection=conn, kodi=kodi)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KodiConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.connection.close()

    return unload_ok
