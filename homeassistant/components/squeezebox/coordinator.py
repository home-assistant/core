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

# Sample status
# {'info total genres': 134, 'newversion': 'A new version of Logitech Media Server is available (8.5.2 - 0). <a href="updateinfo.html?installerFile=/var/lib/squeezeboxserver/cache/updates/logitechmediaserver_8.5.2_amd64.deb" target="update">Click here for further information</a>.', 'httpport': '9000', 'lastscan': '1718431678', 'info total artists': 1954, 'info total albums': 1699, 'player count': 3, 'uuid': 'blargs-blarg-blargle', 'other player count': 2, 'version': '8.5.1', 'ip': '192.168.78.20', 'info total duration': 5036321.37400003, 'mac': '44:1e:a1:3b:78:23', 'info total songs': 20479}
# {'lastscan': '1720418978', 'version': '8.5.1', 'newversion': 'A new version of Logitech Media Server is available (8.5.2 - 0). <a href="updateinfo.html?installerFile=/var/lib/squeezeboxserver/cache/updates/logitechmediaserver_8.5.2_amd64.deb" target="update">Click here for further information</a>.', 'uuid': 'wobble', 'mac': '44:1e:a1:3b:78:23', 'ip': '192.168.78.20', 'httpport': '9000', 'info total albums': 1702, 'info total artists': 1955, 'info total genres': 135, 'info total songs': 20575, 'info total duration': 5057231.58200003, 'player count': 4, 'other player count': 2}
# {'ip': '192.168.78.86', 'info total duration': 364692.599999999, 'lastscan': '1720450648', 'other player count': 4, 'info total genres': 25, 'newplugins': 'Plugins have been updated - Restart Required (Material Skin)', 'uuid': 'wibble', 'info total albums': 69, 'player count': 2, 'needsrestart': 1, 'version': '8.5.2', 'info total songs': 1508, 'info total artists': 117, 'httpport': '9000'}


class LMSStatusDataUpdateCoordinator(DataUpdateCoordinator):
    """LMS Status custom coordinator."""

    def __init__(self, hass: HomeAssistant, my_api: Server) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=my_api.name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=SENSOR_UPDATE_INTERVAL),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=False,
        )
        self.my_api = my_api
        self.newversion_regex = re.compile("<.*$")

    async def _async_update_data(self):
        """Fetch data fromn LMS status call.

        We procees only a subset to make then nice for HA
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with timeout(STATUS_API_TIMEOUT):
                # Grab active context variables to limit data required to be fetched from API
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
                data[STATUS_SENSOR_RESCAN] = (
                    STATUS_SENSOR_RESCAN in data and True or False
                )
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
                    STATUS_SENSOR_NEWPLUGINS in data
                    and data[STATUS_SENSOR_NEWPLUGINS]
                    or None
                )

                # "info total duration"  in fractions of seconds
                # progressdone	Returned with the current value of items completed for current scan phase. Not returned if no scan is in progress.
                # progresstotal	Returned with the total value of items found for current scan phase. Not returned if no scan is in progress.
                # lastscanfailed Information about a possible failure in case a scan has not finished in an attended manner.
                # ip ...
                _LOGGER.debug("Processed serverstatus %s=%s", self.my_api.name, data)
                return data
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with API({self.my_api.name}"
            ) from err
