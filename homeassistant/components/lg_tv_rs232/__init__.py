"""The LG TV RS-232 integration."""

from lg_rs232_tv import LGTV, TVState

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SET_ID, LOGGER, QUERY_ATTRIBUTES, LGTVRS232ConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: LGTVRS232ConfigEntry) -> bool:
    """Set up LG TV RS-232 from a config entry."""
    port = entry.data[CONF_DEVICE]
    tv = LGTV(port, set_id=entry.data[CONF_SET_ID])

    try:
        await tv.connect()
        await tv.query(QUERY_ATTRIBUTES)
    except (ConnectionError, OSError, TimeoutError) as err:
        if tv.connected:
            await tv.disconnect()
        raise ConfigEntryNotReady(f"Error connecting to LG TV: {err}") from err

    entry.runtime_data = tv

    @callback
    def _on_disconnect(state: TVState | None) -> None:
        # Only reload if the entry is still loaded. During entry removal,
        # disconnect() fires this callback but the entry is already gone.
        if state is None and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("LG TV disconnected, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(tv.subscribe(_on_disconnect))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LGTVRS232ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.disconnect()

    return unload_ok
