"""Coordinator for the bzutech integration."""

from datetime import timedelta
import logging
from typing import Any

from bzutech import BzuTech

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHIPID, CONF_SENSORNAME, DOMAIN


class BzuCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Set up coordinator."""

    def __init__(self, hass: HomeAssistant, entry: dict[str, Any]) -> None:
        """Set up coordinator."""
        self.bzu = BzuTech(entry[CONF_EMAIL], entry[CONF_PASSWORD])
        self.chipid = entry[CONF_CHIPID]
        self.sensor = entry[CONF_SENSORNAME]
        self.started = False
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
        except KeyError as error:
            self.started = False
            raise UpdateFailed(error) from error
