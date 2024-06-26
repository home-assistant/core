"""The NWS coordinator."""

from datetime import datetime
import logging

from aiohttp import ClientResponseError
from pynws import NwsNoDataError, SimpleNWS, call_with_retry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import debounce
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow

from .const import (
    DEBOUNCE_TIME,
    DEFAULT_SCAN_INTERVAL,
    OBSERVATION_VALID_TIME,
    RETRY_INTERVAL,
    RETRY_STOP,
    UPDATE_TIME_PERIOD,
)

_LOGGER = logging.getLogger(__name__)


class NWSObservationDataUpdateCoordinator(TimestampDataUpdateCoordinator[None]):
    """Class to manage fetching NWS observation data."""

    def __init__(
        self,
        hass: HomeAssistant,
        nws: SimpleNWS,
    ) -> None:
        """Initialize."""
        self.nws = nws
        self.last_api_success_time: datetime | None = None
        self.initialized: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"NWS observation station {nws.station}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            request_refresh_debouncer=debounce.Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
            ),
        )

    async def _async_update_data(self) -> None:
        """Update data via library."""
        if not self.initialized:
            await self._async_first_update_data()
        else:
            await self._async_subsequent_update_data()

    async def _async_first_update_data(self):
        """Update data without retries first."""
        try:
            await self.nws.update_observation(
                raise_no_data=True,
                start_time=utcnow() - UPDATE_TIME_PERIOD,
            )
        except (NwsNoDataError, ClientResponseError) as err:
            raise UpdateFailed(err) from err
        else:
            self.last_api_success_time = utcnow()
        finally:
            self.initialized = True

    async def _async_subsequent_update_data(self) -> None:
        """Update data with retries and caching data over multiple failed rounds."""
        try:
            await call_with_retry(
                self.nws.update_observation,
                RETRY_INTERVAL,
                RETRY_STOP,
                retry_no_data=True,
                start_time=utcnow() - UPDATE_TIME_PERIOD,
            )
        except (NwsNoDataError, ClientResponseError) as err:
            if not self.last_api_success_time or (
                utcnow() - self.last_api_success_time > OBSERVATION_VALID_TIME
            ):
                raise UpdateFailed(err) from err
            _LOGGER.debug(
                "NWS observation update failed, but data still valid. Last success: %s",
                self.last_api_success_time,
            )
        else:
            self.last_api_success_time = utcnow()
