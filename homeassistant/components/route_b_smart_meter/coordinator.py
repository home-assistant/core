"""DataUpdateCoordinator for the Smart Meter B-route integration."""

from dataclasses import dataclass
import logging
import time

from momonga import Momonga, MomongaError, MomongaNeedToReopen

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class BRouteData:
    """Class for data of the B Route."""

    instantaneous_current_r_phase: float
    instantaneous_current_t_phase: float
    instantaneous_power: float
    total_consumption: float


type BRouteConfigEntry = ConfigEntry[BRouteUpdateCoordinator]


@dataclass
class BRouteDeviceInfo:
    """Static device information fetched once at setup."""

    serial_number: str | None = None
    manufacturer_code: str | None = None
    echonet_version: str | None = None


class BRouteUpdateCoordinator(DataUpdateCoordinator[BRouteData]):
    """The B Route update coordinator."""

    device_info_data: BRouteDeviceInfo
    _port_locked: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BRouteConfigEntry,
    ) -> None:
        """Initialize."""

        self.device = entry.data[CONF_DEVICE]
        self.bid = entry.data[CONF_ID]
        self._password = entry.data[CONF_PASSWORD]

        self.api = Momonga(dev=self.device, rbid=self.bid, pwd=self._password)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self.device_info_data = BRouteDeviceInfo()

    async def _async_setup(self) -> None:
        def fetch() -> None:
            self.api.open()
            self._fetch_device_info()

        await self.hass.async_add_executor_job(fetch)

    def _fetch_device_info(self) -> None:
        """Fetch static device information from the smart meter."""
        try:
            self.device_info_data.serial_number = self.api.get_serial_number()
        except MomongaError:
            _LOGGER.debug("Failed to fetch serial number", exc_info=True)

        time.sleep(self.api.internal_xmit_interval)
        try:
            raw = self.api.get_manufacturer_code()
            self.device_info_data.manufacturer_code = raw.hex().upper()
        except MomongaError:
            _LOGGER.debug("Failed to fetch manufacturer code", exc_info=True)

        time.sleep(self.api.internal_xmit_interval)
        try:
            self.device_info_data.echonet_version = self.api.get_standard_version()
        except MomongaError:
            _LOGGER.debug("Failed to fetch ECHONET Lite version", exc_info=True)

    def _get_data(self) -> BRouteData:
        """Get the data from API."""
        current = self.api.get_instantaneous_current()
        return BRouteData(
            instantaneous_current_r_phase=current["r phase current"],
            instantaneous_current_t_phase=current["t phase current"],
            instantaneous_power=self.api.get_instantaneous_power(),
            total_consumption=self.api.get_measured_cumulative_energy(),
        )

    async def _async_update_data(self) -> BRouteData:
        """Update data."""

        def fetch_with_reopen() -> BRouteData:
            try:
                if self._port_locked:
                    _LOGGER.info("Serial port was previously locked. Reopening session")
                    self.api.open()
                    self._port_locked = False
                return self._get_data()
            except MomongaNeedToReopen:
                _LOGGER.info(
                    "Route-B API is closed (likely from a previous recovery). "
                    "Reopening session"
                )
                self.api.open()
                return self._get_data()

        try:
            return await self.hass.async_add_executor_job(fetch_with_reopen)
        except (
            MomongaError,
            RuntimeError,  # The momonga library raises RuntimeError for session/comm failures
        ) as error:
            _LOGGER.warning(
                "Route-B poll failed. Attempting to force-close the serial port to "
                "prevent lockup"
            )
            try:
                await self.hass.async_add_executor_job(self.api.close)
                _LOGGER.info(
                    "Serial port closed cleanly; ready for the next polling cycle"
                )
                self._port_locked = False
            except Exception:
                # If close fails, mark the port as locked so the next cycle attempts a fresh open
                self._port_locked = True
                _LOGGER.exception("Could not close serial port")
            raise UpdateFailed(error) from error
