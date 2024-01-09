"""The BZUTech integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bzutech import BzuTech

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CHIPID, CONF_SENSORNAME, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BZUTech from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data["host"] = "bzutech"
    bzucoordinator = BzuCloudCoordinator(
        hass=hass,
        chipid=entry.data[CONF_CHIPID],
        sensor=entry.data[CONF_SENSORNAME],
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    hass.data[DOMAIN][entry.entry_id] = bzucoordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BzuCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Set up coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        chipid: str,
        sensor: str,
        email,
        password,
    ) -> None:
        """Set up coordinator."""
        self.chipid = chipid
        self.bzu = BzuTech(email, password)
        self.started = False
        self.sensor = sensor
        update_interval = timedelta(seconds=10)

        super().__init__(
            hass=hass,
            name=DOMAIN,
            update_interval=update_interval,
            logger=logging.getLogger("bzucloud"),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        if not self.started:
            self.started = await self.bzu.start()
        try:
            return await self.bzu.get_reading(str(self.chipid), self.sensor)
        except KeyError:
            await self.bzu.start()
            return await self.bzu.get_reading(str(self.chipid), self.sensor)

    def fetch_data(self):
        """Get initial data for sensor."""
        return self.data
