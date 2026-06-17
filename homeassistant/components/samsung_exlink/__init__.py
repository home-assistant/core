"""The Samsung ExLink integration."""

from samsung_exlink import MODELS, SamsungTV, TVState

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, LOGGER, SamsungExLinkConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: HomeAssistant, entry: SamsungExLinkConfigEntry
) -> bool:
    """Set up Samsung ExLink from a config entry."""
    port = entry.data[CONF_DEVICE]
    tv = SamsungTV(port, model=MODELS.get(entry.data.get(CONF_MODEL, "")))

    try:
        await tv.connect()
        # refresh() tolerates a powered-off TV; it only raises on a broken link.
        await tv.refresh()
    except (ConnectionError, OSError, TimeoutError) as err:
        if tv.connected:
            await tv.disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    entry.runtime_data = tv

    @callback
    def _on_disconnect(state: TVState | None) -> None:
        # Only reload if the entry is still loaded. During entry removal,
        # disconnect() fires this callback but the entry is already gone.
        if state is None and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("Samsung TV disconnected, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(tv.subscribe(_on_disconnect))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SamsungExLinkConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.disconnect()

    return unload_ok
