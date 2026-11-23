"""The ESI R2D7 integration."""

from esi_r2d7 import R2D7Connection

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_SYSTEM,
    DOMAIN,
    LINK_ERRORS,
    LOGGER,
    R2D7ConfigEntry,
    redact_port,
)

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: R2D7ConfigEntry) -> None:
    """Set up ESI R2D7 from a config entry."""
    port = entry.data[CONF_DEVICE]
    connection = R2D7Connection(port, entry.data[CONF_SYSTEM])

    try:
        await connection.connect()
    except LINK_ERRORS:
        # No cause: its text can carry the port URL and its API key, and the
        # full exception is logged.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"port": redact_port(port)},
        ) from None

    entry.runtime_data = connection

    @callback
    def _check_link() -> None:
        # Runs on link changes and entry state changes, so a link lost while
        # the platforms were still being set up reloads once the entry loads.
        if not connection.connected and entry.state is ConfigEntryState.LOADED:
            LOGGER.warning("ESI R2D7 serial link lost, reloading config entry")
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(connection.add_listener(_check_link))
    entry.async_on_unload(entry.async_on_state_change(_check_link))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: R2D7ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    await entry.runtime_data.disconnect()
