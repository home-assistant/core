"""Coordinator for Daikin Onecta integration."""

from datetime import datetime, time, timedelta
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
            update_interval=self._determine_update_interval(hass),
        )

        _LOGGER.info(
            "Daikin coordinator initialized with %s interval",
            self.update_interval,
        )

    @property
    def api(self) -> DaikinApi:
        """Return the Daikin API client."""
        return self._daikin_api

    def _scan_ignore(self) -> int:
        """Return the delay after a write before polling resumes."""
        return int(self.options.get("scan_ignore", 30))

    async def _async_update_data_from_cloud(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch the latest device state from Daikin."""
        _LOGGER.debug("Daikin coordinator start _async_update_data")

        devices = self.data or {}
        scan_ignore_value = self._scan_ignore()

        if (
            self.api.last_patch_call is not None
            and (dt_util.utcnow() - self.api.last_patch_call).total_seconds()
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
                    translation_domain=DOMAIN,
                    translation_key="rate_limit_exceeded",
                    retry_after=err.retry_after,
                ) from err
            except OnectaConnectionError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                ) from err

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

                self.update_interval = self._determine_update_interval(self.hass)

        _LOGGER.debug(
            "Daikin coordinator finished _async_update_data, next interval %s",
            self.update_interval,
        )
        return devices

    @override
    async def _async_update_data(self) -> dict[str, DaikinOnectaDevice]:
        """Fetch data for the Home Assistant coordinator interface."""
        return await self._async_update_data_from_cloud()

    def update_settings(self, config_entry: ConfigEntry) -> bool:
        """Apply updated config entry options and report whether they changed."""
        if self.options == config_entry.options:
            return False

        _LOGGER.debug("Daikin coordinator updating settings")
        self.options = config_entry.options
        self.update_interval = self._determine_update_interval(self.hass)
        _LOGGER.info(
            "Daikin coordinator changed interval to '%s'", self.update_interval
        )
        return True

    def _determine_update_interval(self, hass: HomeAssistant) -> timedelta:
        """Determine the next polling interval."""
        now = dt_util.now()
        # Default of low scan minutes interval
        scan_interval = self.options.get("low_scan_interval", 30) * 60
        high_scan_interval = self.options.get("high_scan_interval", 10) * 60
        hs = dt_util.parse_time(self.options.get("high_scan_start", "07:00:00"))
        ls = dt_util.parse_time(self.options.get("low_scan_start", "22:00:00"))
        assert hs is not None
        assert ls is not None
        in_high_frequency_window = self._in_between(now.time(), hs, ls)
        if in_high_frequency_window:
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
            if self._in_between(now.time(), ls, end_time):
                scan_interval = random.randint(60, int(scan_interval))

        if hs != ls:
            boundary = ls if in_high_frequency_window else hs
            next_boundary = datetime.combine(now.date(), boundary, now.tzinfo)
            if next_boundary <= now:
                next_boundary += timedelta(days=1)
            # Keep a valid polling interval when the next boundary is less
            # than one high-frequency interval away. In particular, converting
            # a fractional-second delay to an integer must not result in zero.
            scan_interval = max(
                high_scan_interval,
                min(scan_interval, int((next_boundary - now).total_seconds())),
            )

        return timedelta(seconds=scan_interval)

    @staticmethod
    def _in_between(now: time, start: time, end: time) -> bool:
        """Return whether now is between start and end, including overnight ranges."""
        if start <= end:
            return start <= now < end
        return start <= now or now < end
