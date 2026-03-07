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

MAX_REOPEN_ATTEMPTS = 5
REOPEN_BACKOFF_BASE = 5
REOPEN_BACKOFF_MAX = 60
CONSECUTIVE_FAILURES_BEFORE_PREEMPTIVE_REOPEN = 2


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
    """The B Route update coordinator with automatic session recovery."""

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
        self._consecutive_failures = 0

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

    def _reopen(self) -> None:
        """Close and reopen the momonga session."""
        _LOGGER.warning("Attempting to reopen momonga session")
        try:
            self.api.close()
        except Exception:  # noqa: BLE001 - USB disconnect can raise non-MomongaError
            _LOGGER.debug("Error closing momonga (ignored)", exc_info=True)
        # Recreate the Momonga instance to ensure clean state
        self.api = Momonga(dev=self.device, rbid=self.bid, pwd=self._password)
        self.api.open()
        _LOGGER.info("Momonga session reopened successfully")

    def _get_data_with_recovery(self) -> BRouteData:
        """Get data, automatically recovering from session failures.

        Catches all exceptions (not just MomongaNeedToReopen) because the
        underlying Wi-SUN adapter can throw serial.SerialException, OSError,
        or other low-level exceptions when the USB connection drops.
        """
        # If we've been failing repeatedly, preemptively reopen before trying
        if self._consecutive_failures >= CONSECUTIVE_FAILURES_BEFORE_PREEMPTIVE_REOPEN:
            _LOGGER.info(
                "Preemptive reopen after %d consecutive failures",
                self._consecutive_failures,
            )
            try:
                self._reopen()
            except Exception:  # noqa: BLE001 - best-effort preemptive reopen
                _LOGGER.warning(
                    "Preemptive reopen failed, will try data fetch anyway",
                    exc_info=True,
                )

        try:
            data = self._get_data()
        except Exception as initial_err:  # noqa: BLE001 - USB disconnect causes non-MomongaError
            last_error: Exception = initial_err
            _LOGGER.warning(
                "Data fetch failed (%s: %s), will attempt up to %d reopens",
                type(initial_err).__name__,
                initial_err,
                MAX_REOPEN_ATTEMPTS,
            )
        else:
            self._consecutive_failures = 0
            return data
        for attempt in range(1, MAX_REOPEN_ATTEMPTS + 1):
            backoff = min(
                REOPEN_BACKOFF_BASE * (2 ** (attempt - 1)),
                REOPEN_BACKOFF_MAX,
            )
            time.sleep(backoff)
            try:
                self._reopen()
                data = self._get_data()
            except Exception as err:  # noqa: BLE001 - recovery must handle all errors
                last_error = err
                _LOGGER.warning(
                    "Reopen attempt %d/%d failed (%s: %s)",
                    attempt,
                    MAX_REOPEN_ATTEMPTS,
                    type(err).__name__,
                    err,
                )
            else:
                _LOGGER.info(
                    "Recovery successful on attempt %d/%d",
                    attempt,
                    MAX_REOPEN_ATTEMPTS,
                )
                self._consecutive_failures = 0
                return data

        self._consecutive_failures += 1
        raise UpdateFailed(
            f"Failed to recover after {MAX_REOPEN_ATTEMPTS} attempts"
            f" ({self._consecutive_failures} consecutive poll failures)"
        ) from last_error

    async def _async_update_data(self) -> BRouteData:
        """Update data with automatic session recovery."""
        try:
            return await self.hass.async_add_executor_job(self._get_data_with_recovery)
        except UpdateFailed:
            raise
        except Exception as error:
            self._consecutive_failures += 1
            raise UpdateFailed(
                f"Unexpected error ({type(error).__name__}): {error}"
            ) from error
