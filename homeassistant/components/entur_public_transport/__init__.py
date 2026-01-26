"""The Entur public transport integration."""

from __future__ import annotations

from dataclasses import dataclass
from random import randint

from enturclient import EnturPublicTransportData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_CLIENT_NAME,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
)
from .sensor import EnturProxy

PLATFORMS = [Platform.SENSOR]


@dataclass
class EnturRuntimeData:
    """Runtime data for Entur integration."""

    data: EnturPublicTransportData
    proxy: EnturProxy
    show_on_map: bool


type EnturConfigEntry = ConfigEntry[EnturRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EnturConfigEntry) -> bool:
    """Set up Entur public transport from a config entry."""
    # Get configuration
    config = {**entry.data, **entry.options}
    stop_ids = config[CONF_STOP_IDS]
    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = EnturPublicTransportData(
        API_CLIENT_NAME.format(str(randint(100000, 999999))),
        stops=stops,
        quays=quays,
        line_whitelist=config.get(CONF_WHITELIST_LINES) or [],
        omit_non_boarding=config.get(CONF_OMIT_NON_BOARDING, True),
        number_of_departures=config.get(CONF_NUMBER_OF_DEPARTURES, 2),
        web_session=async_get_clientsession(hass),
    )

    if config.get(CONF_EXPAND_PLATFORMS, True):
        await data.expand_all_quays()
    await data.update()

    proxy = EnturProxy(data)
    entry.runtime_data = EnturRuntimeData(
        data=data,
        proxy=proxy,
        show_on_map=config.get(CONF_SHOW_ON_MAP, False),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: EnturConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EnturConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
