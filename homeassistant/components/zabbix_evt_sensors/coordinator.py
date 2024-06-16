"""Zabbix Data Coordinator."""

import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PROBLEMS_KEY, SERVICES_KEY

_LOGGER = logging.getLogger(__name__)


class ZabbixUpdateCoordinator(DataUpdateCoordinator):
    """Zabbix DataUpdateCoordinator used to retrieve data for all sensors at once."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        zbx,
        name: str = DOMAIN,
        update_interval: int = 30,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=datetime.timedelta(seconds=update_interval),
        )
        self.zbx = zbx

    async def _async_update_data(self):
        return {
            SERVICES_KEY: await self.hass.async_add_executor_job(self.zbx.services),
            PROBLEMS_KEY: await self.hass.async_add_executor_job(self.zbx.problems),
        }
