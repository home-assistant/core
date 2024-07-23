"""DataUpdateCoordinator for the Squeezebox integration."""

from asyncio import timeout
from datetime import timedelta
import logging
import re

from pysqueezebox import Server

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    SENSOR_UPDATE_INTERVAL,
    STATUS_API_TIMEOUT,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_NEEDSRESTART,
    STATUS_SENSOR_NEWPLUGINS,
    STATUS_SENSOR_NEWVERSION,
    STATUS_SENSOR_RESCAN,
)

_LOGGER = logging.getLogger(__name__)


class LMSStatusDataUpdateCoordinator(DataUpdateCoordinator):
    """LMS Status custom coordinator."""

    def __init__(self, hass: HomeAssistant, my_api: Server) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=my_api.name,
            update_interval=timedelta(seconds=SENSOR_UPDATE_INTERVAL),
            always_update=False,
        )
        self.my_api = my_api
        self.newversion_regex = re.compile("<.*$")

    async def _async_update_data(self):
        """Fetch data fromn LMS status call.

        Then we procees only a subset to make then nice for HA
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with timeout(STATUS_API_TIMEOUT):
            data = await self.my_api.async_status()

        if not data:
            raise UpdateFailed("No data from status poll")

        _LOGGER.debug("Raw serverstatus %s=%s", self.my_api.name, data)
        # Sensor that need special handling
        # 'lastscan': '1718431678', epoc -> ISO 8601 not allways present
        data[STATUS_SENSOR_LASTSCAN] = (
            STATUS_SENSOR_LASTSCAN in data
            and dt_util.utc_from_timestamp(int(data[STATUS_SENSOR_LASTSCAN]))
            or None
        )
        # rescan # bool are we rescanning alter poll not allways present
        data[STATUS_SENSOR_RESCAN] = STATUS_SENSOR_RESCAN in data and True or False
        # needsrestart bool plugin updates... not allways present
        data[STATUS_SENSOR_NEEDSRESTART] = (
            STATUS_SENSOR_NEEDSRESTART in data and True or False
        )
        # newversion str not aways present
        # Sample text 'A new version of Logitech Media Server is available (8.5.2 - 0). <a href="updateinfo.html?installerFile=/var/lib/squeezeboxserver/cache/updates/logitechmediaserver_8.5.2_amd64.deb" target="update">Click here for further information</a>.'
        data[STATUS_SENSOR_NEWVERSION] = (
            STATUS_SENSOR_NEWVERSION in data
            and self.newversion_regex.sub("...", data[STATUS_SENSOR_NEWVERSION])
            or None
        )
        # newplugins str not aways present
        data[STATUS_SENSOR_NEWPLUGINS] = (
            STATUS_SENSOR_NEWPLUGINS in data and data[STATUS_SENSOR_NEWPLUGINS] or None
        )

        # "info total duration"  in fractions of seconds
        # progressdone	Returned with the current value of items completed for current scan phase. Not returned if no scan is in progress.
        # progresstotal	Returned with the total value of items found for current scan phase. Not returned if no scan is in progress.
        # lastscanfailed Information about a possible failure in case a scan has not finished in an attended manner.
        _LOGGER.debug("Processed serverstatus %s=%s", self.my_api.name, data)
        return data
