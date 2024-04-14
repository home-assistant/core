"""The data update coordinator for OctoPrint."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

from pyoctoprintapi import ApiError, OctoprintClient, PrinterOffline
from pyoctoprintapi.exceptions import UnauthorizedException
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OctoprintDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Octoprint data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        octoprint: OctoprintClient,
        config_entry: ConfigEntry,
        interval: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"octoprint-{config_entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.config_entry = config_entry
        self._octoprint = octoprint
        self._printer_offline = False
        self.data = {"printer": None, "job": None, "last_read_time": None}

    async def _async_update_data(self):
        """Update data via API."""
        printer = None
        try:
            job = await self._octoprint.get_job_info()
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(err) from err

        # If octoprint is on, but the printer is disconnected
        # printer will return a 409, so continue using the last
        # reading if there is one
        try:
            printer = await self._octoprint.get_printer_info()
        except PrinterOffline:
            if not self._printer_offline:
                _LOGGER.debug("Unable to retrieve printer information: Printer offline")
                self._printer_offline = True
        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(err) from err
        else:
            self._printer_offline = False

        return {"job": job, "printer": printer, "last_read_time": dt_util.utcnow()}

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = cast(str, self.config_entry.unique_id)
        configuration_url = URL.build(
            scheme=self.config_entry.data[CONF_SSL] and "https" or "http",
            host=self.config_entry.data[CONF_HOST],
            port=self.config_entry.data[CONF_PORT],
            path=self.config_entry.data[CONF_PATH],
        )

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="OctoPrint",
            name="OctoPrint",
            configuration_url=str(configuration_url),
        )
