"""The ESI R2D7 integration."""

from esi_r2d7 import CONNECT_ERRORS, R2D7Connection

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SYSTEM, DOMAIN, LOGGER, R2D7ConfigEntry, redact_port

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: R2D7ConfigEntry) -> None:
    """Set up ESI R2D7 from a config entry."""
    port = entry.data[CONF_DEVICE]
    connection = R2D7Connection(port, entry.data[CONF_SYSTEM])

    try:
        await connection.connect()
    except CONNECT_ERRORS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"port": redact_port(port)},
        ) from err

    entry.runtime_data = connection

    @callback
    def _on_link_change() -> None:
        # Only reload if the entry is still loaded. During entry removal,
        # disconnect() fires this callback but the entry is already gone.
        if not connection.connected and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("ESI R2D7 serial link lost, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(connection.add_listener(_on_link_change))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: R2D7ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    await entry.runtime_data.disconnect()
