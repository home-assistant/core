"""The Lutron GRAFIK Eye integration."""

import logging

from grafikeye import (
    GrafikEyeAuthenticationError,
    GrafikEyeClient,
    GrafikEyeConnectionError,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

PLATFORMS = [Platform.SELECT]

type GrafikEyeConfigEntry = ConfigEntry[GrafikEyeClient]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrafikEyeConfigEntry,
) -> None:
    """Set up Lutron GRAFIK Eye from a config entry."""
    client = GrafikEyeClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        login=entry.data[CONF_PASSWORD],
    )

    try:
        await client.connect()
    except GrafikEyeAuthenticationError as error:
        raise ConfigEntryAuthFailed from error
    except GrafikEyeConnectionError as error:
        raise ConfigEntryNotReady from error

    entry.runtime_data = client

    @callback
    def on_disconnect() -> None:
        if entry.state is ConfigEntryState.LOADED:
            _LOGGER.warning(
                "Connection to GRAFIK Eye Ethernet interface lost, reloading integration"
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(client.register_disconnect_callback(on_disconnect))

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.disconnect()
        raise


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GrafikEyeConfigEntry,
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.disconnect()
