"""The VLC media player Telnet integration."""
from python_telnet_vlc import AuthError, ConnectionError as ConnErr, VLCTelnet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DATA_AVAILABLE, DATA_VLC, DOMAIN, LOGGER

PLATFORMS = ["media_player"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VLC media player Telnet from a config entry."""
    config = entry.data

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    password = config[CONF_PASSWORD]

    vlc = VLCTelnet(host, password, port, connect=False, login=False)

    available = True

    try:
        await hass.async_add_executor_job(vlc.connect)
    except (ConnErr, EOFError) as err:
        LOGGER.warning("Failed to connect to VLC: %s. Trying again", err)
        available = False

    if available:
        try:
            await hass.async_add_executor_job(vlc.login)
        except AuthError as err:
            await hass.async_add_executor_job(disconnect_vlc, vlc)
            raise ConfigEntryAuthFailed() from err

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = {DATA_VLC: vlc, DATA_AVAILABLE: available}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        vlc = entry_data[DATA_VLC]

        await hass.async_add_executor_job(disconnect_vlc, vlc)

    return unload_ok


def disconnect_vlc(vlc: VLCTelnet) -> None:
    """Disconnect from VLC."""
    LOGGER.debug("Disconnecting from VLC")
    try:
        vlc.disconnect()
    except (ConnErr, EOFError) as err:
        LOGGER.warning("Connection error: %s", err)
