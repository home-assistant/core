"""The trafikverket_train component."""
from __future__ import annotations

from pytrafikverket import TrafikverketTrain

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_FROM, CONF_TO, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafikverket Train from a config entry."""

    http_session = async_get_clientsession(hass)
    train_api = TrafikverketTrain(http_session, entry.data[CONF_API_KEY])

    try:
        to_station = await train_api.async_get_train_station(entry.data[CONF_TO])
        from_station = await train_api.async_get_train_station(entry.data[CONF_FROM])
    except ValueError as error:
        if "Invalid authentication" in error.args[0]:
            raise ConfigEntryAuthFailed from error
        raise ConfigEntryNotReady(
            f"Problem when trying station {entry.data[CONF_FROM]} to"
            f" {entry.data[CONF_TO]}. Error: {error} "
        ) from error

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONF_TO: to_station,
        CONF_FROM: from_station,
        "train_api": train_api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Trafikverket Weatherstation config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
