"""The TED integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
import httpx
import tedpy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR, DOMAIN, NAME, PLATFORMS

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Envoy from a config entry."""

    config = entry.data
    name = config[CONF_NAME]

    async with async_timeout.timeout(10):
        ted_reader = await tedpy.createTED(
            config[CONF_HOST],
            async_client=get_async_client(hass),
        )

    async def async_update_data():
        """Fetch data from API endpoint."""
        data = {}
        async with async_timeout.timeout(10):
            try:
                await ted_reader.update()
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            consumption = ted_reader.total_consumption()
            data["is_5000"] = isinstance(ted_reader, tedpy.TED5000)
            data["consumption"] = consumption.now
            data["daily_consumption"] = consumption.daily
            data["mtd_consumption"] = consumption.mtd
            data["spyders"] = {}
            for spyder in ted_reader.spyders:
                for ctgroup in spyder.ctgroups:
                    consumption = ted_reader.spyder_ctgroup_consumption(spyder, ctgroup)
                    data["spyders"][f"{spyder.position}.{ctgroup.position}"] = {
                        "name": ctgroup.description,
                        "consumption": consumption.now,
                        "daily_consumption": consumption.daily,
                        "mtd_consumption": consumption.mtd,
                    }
            data["mtus"] = {}
            for mtu in ted_reader.mtus:
                consumption = ted_reader.mtu_consumption(mtu)
                data["mtus"][mtu.position] = {
                    "name": mtu.description,
                    "consumption": consumption.current_usage,
                    "voltage": consumption.voltage,
                }

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"TED {name}",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        NAME: name,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
