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
    """Set up TED from a config entry."""
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

            data["type"] = ted_reader.system_type
            data["energy"] = ted_reader.energy()
            data["production"] = ted_reader.production()
            data["consumption"] = ted_reader.consumption()
            data["spyders"] = {}
            for spyder in ted_reader.spyders:
                for ctgroup in spyder.ctgroups:
                    data["spyders"][f"{spyder.position}.{ctgroup.position}"] = {
                        "name": ctgroup.description,
                        "energy": ctgroup.energy(),
                    }
            data["mtus"] = {}
            for mtu in ted_reader.mtus:
                data["mtus"][mtu.position] = {
                    "name": mtu.description,
                    "type": mtu.type,
                    "power": mtu.power(),
                    "energy": mtu.energy(),
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
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
