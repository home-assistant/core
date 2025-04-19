"""The Swing2Sleep Smarla integration."""

from pysmarlaapi import Connection, Federwiege

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, HOST, PLATFORMS

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type FederwiegeConfigEntry = ConfigEntry[Federwiege]


async def async_setup_entry(hass: HomeAssistant, entry: FederwiegeConfigEntry) -> bool:
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    try:
        connection = Connection(HOST, token_str=entry.data.get(CONF_ACCESS_TOKEN, None))
    except ValueError as e:
        raise ConfigEntryError("Invalid token") from e

    if not await connection.get_token():
        raise ConfigEntryAuthFailed("Invalid authentication")

    federwiege = Federwiege(hass.loop, connection)
    federwiege.register()
    federwiege.connect()

    entry.runtime_data = federwiege

    await hass.config_entries.async_forward_entry_setups(
        entry,
        list(PLATFORMS),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FederwiegeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        list(PLATFORMS),
    )

    if unload_ok:
        federwiege = entry.runtime_data
        federwiege.disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
