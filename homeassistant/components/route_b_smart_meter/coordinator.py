"""DataUpdateCoordinator for the Smart Meter B-route integration."""

from dataclasses import dataclass
import logging
import time

from momonga import Momonga, MomongaError

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
        try:
            return await self.hass.async_add_executor_job(self._get_data)
        except MomongaError as error:
            raise UpdateFailed(error) from error
