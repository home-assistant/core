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
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_NEEDSRESTART,
    STATUS_SENSOR_NEWPLUGINS,
    STATUS_SENSOR_NEWVERSION,
    STATUS_SENSOR_RESCAN,
)

_LOGGER = logging.getLogger(__name__)


class LMSStatusDataUpdateCoordinator(DataUpdateCoordinator):
    """LMS Status custom coordinator."""

    def __init__(self, hass: HomeAssistant, lms: Server) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=lms.name,
            update_interval=timedelta(seconds=SENSOR_UPDATE_INTERVAL),
            always_update=False,
        )
        self.lms = lms
        self.can_server_restart = False
        self.newversion_regex_pre = re.compile("^.*\\(")
        self.newversion_regex_post = re.compile("\\)\\. <.*$")
        self.newversion_regex_windows_pre = re.compile("^<ul><li>[\\S]+ ")
        self.newversion_regex_windows_post = re.compile("[\\D]*</li><li>.*$")
        self.newplugins_regex = re.compile(".* - ")

    async def _async_setup(self) -> None:
        """Query LMS capabilities."""
        result = await self.lms.async_query("can", "restartserver", "?")
        if result and "_can" in result and result["_can"] == 1:
            _LOGGER.debug("Can restart %s", self.lms.name)
            self.can_server_restart = True
        else:
            _LOGGER.warning("Can't query server capabilities %s", self.lms.name)

    async def _async_update_data(self) -> dict:
        """Fetch data fromn LMS status call.

        Then we process only a subset to make then nice for HA
        """
        async with timeout(STATUS_API_TIMEOUT):
            data = await self.lms.async_status()

        if not data:
            raise UpdateFailed(f"No data from status poll for {self.lms.name}")
        _LOGGER.debug("Raw serverstatus %s=%s", self.lms.name, data)

        return self._prepare_status_data(data)

    def _prepare_status_data(self, data: dict) -> dict:
        """Sensors that need the data changing for HA presentation."""

        # Binary sensors
        # rescan bool are we rescanning alter poll not present if false
        data[STATUS_SENSOR_RESCAN] = STATUS_SENSOR_RESCAN in data
        # needsrestart bool pending lms plugin updates not present if false
        data[STATUS_SENSOR_NEEDSRESTART] = STATUS_SENSOR_NEEDSRESTART in data

        # Sensors that need special handling
        # 'lastscan': '1718431678', epoc -> ISO 8601 not always present
        data[STATUS_SENSOR_LASTSCAN] = (
            dt_util.utc_from_timestamp(int(data[STATUS_SENSOR_LASTSCAN]))
            if STATUS_SENSOR_LASTSCAN in data
            else None
        )

        # Updates
        # newversion str not always present
        # Sample text:-
        # 'A new version of Logitech Media Server is available (8.5.2 - 0). <a href="updateinfo.html?installerFile=/var/lib/squeezeboxserver/cache/updates/logitechmediaserver_8.5.2_amd64.deb" target="update">Click here for further information</a>.'
        # '<ul><li>Version %s - %s is available for installation.</li><li>Log in to your computer running Logitech Media Server (%s).</li><li>Execute <code>%s</code> and follow the instructions.</li></ul>'
        data[STATUS_SENSOR_NEWVERSION] = (
            self.newversion_regex_pre.sub(
                "",
                self.newversion_regex_post.sub(
                    "",
                    self.newversion_regex_windows_pre.sub(
                        "",
                        self.newversion_regex_windows_post.sub(
                            "", data[STATUS_SENSOR_NEWVERSION]
                        ),
                    ),
                ),
            )
            if STATUS_SENSOR_NEWVERSION in data
            else data[STATUS_QUERY_VERSION]
        )
        # newplugins str not always present
        # newplugins': 'Plugins have been updated - Restart Required (BBC Sounds)
        data[STATUS_SENSOR_NEWPLUGINS] = (
            self.newplugins_regex.sub("", data[STATUS_SENSOR_NEWPLUGINS])
            if STATUS_SENSOR_NEWPLUGINS in data
            else "current"
        )

        _LOGGER.debug("Processed serverstatus %s=%s", self.lms.name, data)
        return data
