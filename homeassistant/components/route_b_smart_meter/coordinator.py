"""DataUpdateCoordinator for the Smart Meter B-route integration."""

from dataclasses import dataclass
from datetime import datetime
import logging
import time

from momonga import Momonga, MomongaError
from momonga.momonga_exception import MomongaNeedToReopen

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_REOPEN_ATTEMPTS = 3
REOPEN_BACKOFF_SECONDS = 10


@dataclass
class BRouteDeviceInfo:
    """Static device information fetched once at setup."""

    serial_number: str | None = None
    manufacturer_code: str | None = None
    echonet_version: str | None = None


@dataclass
class BRouteData:
    """Class for data of the B Route."""

    instantaneous_current_r_phase: float
    instantaneous_current_t_phase: float
    instantaneous_power: float
    total_consumption: float
    meter_timestamp: datetime | None = None
    fault_status: bool | None = None


type BRouteConfigEntry = ConfigEntry[BRouteUpdateCoordinator]


class BRouteUpdateCoordinator(DataUpdateCoordinator[BRouteData]):
    """The B Route update coordinator."""

    device_info_data: BRouteDeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BRouteConfigEntry,
    ) -> None:
        """Initialize."""

        self.device = entry.data[CONF_DEVICE]
        self.bid = entry.data[CONF_ID]
        self._password = entry.data[CONF_PASSWORD]
        self.device_info_data = BRouteDeviceInfo()

        self.api = Momonga(dev=self.device, rbid=self.bid, pwd=self._password)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_setup(self) -> None:
        await self.hass.async_add_executor_job(self.api.open)
        await self.hass.async_add_executor_job(self._fetch_device_info)

    def _fetch_device_info(self) -> None:
        """Fetch static device information from API."""
        try:
            self.device_info_data.serial_number = self.api.get_serial_number()
        except MomongaError:
            _LOGGER.debug("Failed to fetch serial number", exc_info=True)

        time.sleep(self.api.internal_xmit_interval)
        try:
            manufacturer_code = self.api.get_manufacturer_code()
            self.device_info_data.manufacturer_code = manufacturer_code.hex().upper()
        except MomongaError:
            _LOGGER.debug("Failed to fetch manufacturer code", exc_info=True)

        time.sleep(self.api.internal_xmit_interval)
        try:
            self.device_info_data.echonet_version = self.api.get_standard_version()
        except MomongaError:
            _LOGGER.debug("Failed to fetch ECHONET Lite version", exc_info=True)

    def _reopen(self) -> None:
        """Reopen Momonga session."""
        try:
            self.api.close()
        except MomongaError:
            _LOGGER.debug("Error closing Momonga before reopen", exc_info=True)
        self.api = Momonga(dev=self.device, rbid=self.bid, pwd=self._password)
        self.api.open()

    def _get_data(self) -> BRouteData:
        """Get the data from API."""
        current = self.api.get_instantaneous_current()
        data = BRouteData(
            instantaneous_current_r_phase=current["r phase current"],
            instantaneous_current_t_phase=current["t phase current"],
            instantaneous_power=self.api.get_instantaneous_power(),
            total_consumption=self.api.get_measured_cumulative_energy(),
        )

        time.sleep(self.api.internal_xmit_interval)
        try:
            fixed_time_energy = self.api.get_cumulative_energy_measured_at_fixed_time()
            data.meter_timestamp = fixed_time_energy.get("timestamp")
        except MomongaError:
            _LOGGER.debug(
                "Failed to fetch cumulative energy measured at fixed time", exc_info=True
            )

        time.sleep(self.api.internal_xmit_interval)
        try:
            data.fault_status = self.api.get_fault_status()
        except MomongaError:
            _LOGGER.debug("Failed to fetch fault status", exc_info=True)

        return data

    def _get_data_with_recovery(self) -> BRouteData:
        """Get data and recover by reopening session if needed."""
        try:
            return self._get_data()
        except MomongaNeedToReopen as error:
            last_error: MomongaError = error

        for attempt in range(1, MAX_REOPEN_ATTEMPTS + 1):
            _LOGGER.warning(
                "Momonga session requires reopen (attempt %s/%s)",
                attempt,
                MAX_REOPEN_ATTEMPTS,
            )
            try:
                self._reopen()
                return self._get_data()
            except MomongaNeedToReopen as error:
                last_error = error
                if attempt < MAX_REOPEN_ATTEMPTS:
                    time.sleep(REOPEN_BACKOFF_SECONDS)

        raise MomongaError("Failed to recover Momonga session") from last_error

    async def _async_update_data(self) -> BRouteData:
        """Update data."""
        try:
            return await self.hass.async_add_executor_job(self._get_data_with_recovery)
        except MomongaError as error:
            raise UpdateFailed(error) from error
