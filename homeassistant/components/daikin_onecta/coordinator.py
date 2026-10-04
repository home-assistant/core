"""Coordinator for Daikin Onecta integration."""

from datetime import time, timedelta
import logging
import random
from typing import override

from daikin_onecta.exceptions import OnectaConnectionError, OnectaRateLimitError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .daikin_api import DaikinApi
from .device import DaikinOnectaDevice

_LOGGER = logging.getLogger(__name__)
RATE_LIMIT_EXCEEDED = "Daikin API rate limit exceeded"
CONNECTION_FAILED = "Unable to connect to the Daikin API"


class OnectaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DaikinOnectaDevice]]):
    """Class to manage fetching data from the API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, daikin_api: DaikinApi
    ) -> None:
        """Initialize."""
        self.options = config_entry.options
        self._config_entry = config_entry
        self._daikin_api = daikin_api

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self.determine_update_interval(hass),
        )

        _LOGGER.info(
            "Daikin coordinator initialized with %s interval",
            self.update_interval,
        )

    @property
    def api(self) -> DaikinApi:
        """Return the Daikin API client."""
        return self._daikin_api

    def scan_ignore(self) -> int:
        """Return the delay after a write before polling resumes."""
        return self.options.get("scan_ignore", 30)

    async def async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch the latest device state from Daikin."""
        _LOGGER.debug("Daikin coordinator start _async_update_data")

        devices = self.data or {}
        scan_ignore_value = self.scan_ignore()

        if (
            self.api.last_patch_call is not None
            and (dt_util.now() - self.api.last_patch_call).total_seconds()
            < scan_ignore_value
        ):
            self.update_interval = timedelta(seconds=scan_ignore_value)
            _LOGGER.debug(
                "API UPDATE skipped (just updated from UI)",
            )
        else:
            try:
                cloud_devices = await self.api.get_cloud_device_details(
                    cooldown=timedelta(seconds=scan_ignore_value)
                )
            except OnectaRateLimitError as err:
                _LOGGER.warning(
                    "Daikin API rate limit reached; retrying after %s seconds",
                    err.retry_after,
                )
                raise UpdateFailed(
                    RATE_LIMIT_EXCEEDED,
                    retry_after=err.retry_after,
                ) from err
            except OnectaConnectionError as err:
                raise UpdateFailed(CONNECTION_FAILED) from err

            if cloud_devices is None:
                self.update_interval = timedelta(seconds=scan_ignore_value)
                _LOGGER.debug("API UPDATE skipped (just updated from UI)")
            else:
                cloud_device_ids = {device.id for device in cloud_devices}
                for device_id, device in devices.items():
                    if device_id not in cloud_device_ids:
                        device.mark_unavailable()

                for dev_data in cloud_devices:
                    if dev_data.id in devices:
                        devices[dev_data.id].set_device_data(dev_data)
                    else:
                        device = DaikinOnectaDevice(dev_data, self.api)
                        # Register the gateway device before entity platforms are set
                        # up so they can link back to this gateway device.
                        device.async_register_ha_device(self.hass, self._config_entry)
                        devices[dev_data.id] = device

                self.update_interval = self.determine_update_interval(self.hass)

        _LOGGER.debug(
            "Daikin coordinator finished _async_update_data, next interval %s",
            self.update_interval,
        )
        return devices

    @override
    async def _async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch data for the Home Assistant coordinator interface."""
        return await self.async_update_data()

    def update_settings(self, config_entry: ConfigEntry) -> None:
        """Apply updated config entry options."""
        _LOGGER.debug("Daikin coordinator updating settings")
        self.options = config_entry.options
        self.update_interval = self.determine_update_interval(self.hass)
        _LOGGER.info(
            "Daikin coordinator changed interval to '%s'", self.update_interval
        )

    def determine_update_interval(self, hass: HomeAssistant) -> timedelta:
        """Determine the next polling interval."""
        # Default of low scan minutes interval
        scan_interval = self.options.get("low_scan_interval", 30) * 60
        high_scan_interval = self.options.get("high_scan_interval", 10) * 60
        hs = dt_util.parse_time(self.options.get("high_scan_start", "07:00:00"))
        ls = dt_util.parse_time(self.options.get("low_scan_start", "22:00:00"))
        assert hs is not None
        assert ls is not None
        if self.in_between(dt_util.now().time(), hs, ls):
            scan_interval = high_scan_interval
        else:
            # When switching from high to low frequency polling we need to randomize the first
            # poll so that we spread the load to daikin, so for example when we have a low start at
            # 22:00 and a high scan interval of 9 minutes we randomize the next poll when it is
            # between 22:00 and 22:09
            end_time = (
                dt_util.start_of_local_day()
                + timedelta(
                    hours=ls.hour,
                    minutes=ls.minute,
                    seconds=ls.second + high_scan_interval,
                )
            ).time()
            if self.in_between(dt_util.now().time(), ls, end_time):
                scan_interval = random.randint(60, int(scan_interval))

        return timedelta(seconds=scan_interval)

    @staticmethod
    def in_between(now: time, start: time, end: time) -> bool:
        """Return whether now is between start and end, including overnight ranges."""
        if start <= end:
            return start <= now < end
        return start <= now or now < end
