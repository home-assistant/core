"""The Swing2Sleep Smarla integration."""

from pysmarlaapi import Connection, Federwiege
from pysmarlaapi.connection.exceptions import (
    AuthenticationException,
    ConnectionException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import HOST, PLATFORMS

type FederwiegeConfigEntry = ConfigEntry[Federwiege]


async def async_setup_entry(hass: HomeAssistant, entry: FederwiegeConfigEntry) -> bool:
    """Set up this integration using UI."""
    connection = Connection(HOST, token_b64=entry.data[CONF_ACCESS_TOKEN])

    # Check if token still has access
    try:
        await connection.refresh_token()
    except (ConnectionException, AuthenticationException) as e:
        raise ConfigEntryError("Invalid authentication") from e

    federwiege = Federwiege(hass.loop, connection)
    federwiege.register()

    entry.runtime_data = federwiege

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    federwiege.connect()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FederwiegeConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.disconnect()

    return unload_ok
