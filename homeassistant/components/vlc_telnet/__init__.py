"""The VLC media player Telnet integration."""

from dataclasses import dataclass

from aiovlc.client import Client
from aiovlc.exceptions import AuthError, ConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import LOGGER

PLATFORMS = [Platform.MEDIA_PLAYER]

type VlcConfigEntry = ConfigEntry[VlcData]


@dataclass
class VlcData:
    """Runtime data definition."""

    vlc: Client
    available: bool


async def async_setup_entry(hass: HomeAssistant, entry: VlcConfigEntry) -> bool:
    """Set up VLC media player Telnet from a config entry."""
    config = entry.data

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    password = config[CONF_PASSWORD]

    vlc = Client(password=password, host=host, port=port)

    available = True

    try:
        await vlc.connect()
    except ConnectError as err:
        LOGGER.warning("Failed to connect to VLC: %s. Trying again", err)
        available = False

    async def _disconnect_vlc() -> None:
        """Disconnect from VLC."""
        LOGGER.debug("Disconnecting from VLC")
        try:
            await vlc.disconnect()
        except ConnectError as err:
            LOGGER.warning("Connection error: %s", err)

    if available:
        try:
            await vlc.login()
        except AuthError as err:
            await _disconnect_vlc()
            raise ConfigEntryAuthFailed from err

    entry.runtime_data = VlcData(vlc, available)

    entry.async_on_unload(_disconnect_vlc)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
