"""The Russound RNET integration."""

from contextlib import suppress

from aiorussound.connection import (
    RussoundConnectionHandler,
    RussoundSerialConnectionHandler,
    RussoundTcpConnectionHandler,
)
from aiorussound.rnet.client import RussoundRNETClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_BAUDRATE, RNET_EXCEPTIONS, TYPE_TCP

type RussoundRNETConfigEntry = ConfigEntry[RussoundRNETClient]

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Set up Russound RNET from a config entry."""
    handler: RussoundConnectionHandler
    if entry.data[CONF_TYPE] == TYPE_TCP:
        handler = RussoundTcpConnectionHandler(
            entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    else:
        handler = RussoundSerialConnectionHandler(
            entry.data[CONF_DEVICE], DEFAULT_BAUDRATE
        )

    client = RussoundRNETClient(handler)

    try:
        await client.connect()
    except RNET_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Russound RNET device: {err}"
        ) from err

    entry.runtime_data = client

    async def _async_disconnect() -> None:
        with suppress(*RNET_EXCEPTIONS):
            await client.disconnect()

    entry.async_on_unload(_async_disconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RussoundRNETConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
