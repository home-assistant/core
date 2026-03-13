"""The Entur public transport integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from random import randint

from enturclient import EnturPublicTransportData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import (
    API_CLIENT_NAME,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
)

PLATFORMS = [Platform.SENSOR]


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on the API.
    """

    def __init__(self, api: EnturPublicTransportData) -> None:
        """Initialize the proxy."""
        self._api = api

    @Throttle(timedelta(seconds=15))
    async def async_update(self) -> None:
        """Update data in client."""
        await self._api.update()

    def get_stop_info(self, stop_id: str):
        """Get info about specific stop place."""
        return self._api.get_stop_info(stop_id)


@dataclass
class EnturRuntimeData:
    """Runtime data for Entur integration."""

    data: EnturPublicTransportData
    proxy: EnturProxy
    show_on_map: bool


type EnturConfigEntry = ConfigEntry[EnturRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: EnturConfigEntry) -> bool:
    """Set up Entur public transport from a config entry."""
    stop_ids = entry.data[CONF_STOP_IDS]
    stops = [s for s in stop_ids if "StopPlace" in s]
    quays = [s for s in stop_ids if "Quay" in s]

    data = EnturPublicTransportData(
        API_CLIENT_NAME.format(str(randint(100000, 999999))),
        stops=stops,
        quays=quays,
        line_whitelist=entry.options.get(CONF_WHITELIST_LINES, []),
        omit_non_boarding=entry.options.get(CONF_OMIT_NON_BOARDING, True),
        number_of_departures=entry.options.get(CONF_NUMBER_OF_DEPARTURES, 2),
        web_session=async_get_clientsession(hass),
    )

    await data.expand_all_quays()
    await data.update()

    proxy = EnturProxy(data)
    entry.runtime_data = EnturRuntimeData(
        data=data,
        proxy=proxy,
        show_on_map=entry.options.get(CONF_SHOW_ON_MAP, False),
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
