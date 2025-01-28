"""Define the BRouteDataCoordinator class."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .broute_reader import BRouteReader
from .const import DEFAULT_RETRY_COUNT, DEFAULT_UPDATE_INTERVAL, DEVICE_NAME

_LOGGER = logging.getLogger(__name__)


class BRouteDataCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from B-route meter.

    Schedules regular data fetch. We'll store or reuse the BRouteReader,
    and run its get_data() in a thread pool.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        route_b_id,
        route_b_pwd,
        serial_port,
        retry_count=DEFAULT_RETRY_COUNT,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DEVICE_NAME,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.reader = BRouteReader(route_b_id, route_b_pwd, serial_port)
        self.retry_count = retry_count
        self._is_connected = False
        self._connection_lock = asyncio.Lock()

    async def _try_connect(self):
        """Connect to the meter and set the connection status."""
        if not self._is_connected:
            _LOGGER.info("Try connecting to B-Route meter")
            try:
                await self.hass.async_add_executor_job(self.reader.connect)
                self._is_connected = True
                _LOGGER.info("Successfully connected to B-Route meter")
            except Exception as err:
                self._is_connected = False
                _LOGGER.error("Failed to connect to B-Route meter: %s", err)
                raise UpdateFailed("Failed to connect to B-Route meter") from err

    def _raise_update_failed(self, message):
        """Raise an UpdateFailed exception with the given message."""
        raise UpdateFailed(message)

    async def _async_update_data(self):
        """Fetch data from B-route meter."""
        async with self._connection_lock:
            for attempt in range(self.retry_count):
                try:
                    if not self._is_connected:
                        await self._try_connect()

                    data = await self.hass.async_add_executor_job(self.reader.get_data)
                    if data is None:
                        self._raise_update_failed("Received empty data from meter")
                    else:
                        return data
                except Exception as err:
                    self._is_connected = False  # Reset connection status
                    last_error = str(err)

                    if attempt + 1 < self.retry_count:
                        _LOGGER.warning(
                            "Update attempt %d/%d failed: %s. Retrying in 2^%d seconds",
                            attempt + 1,
                            self.retry_count,
                            last_error,
                            2**attempt,
                        )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        _LOGGER.error(
                            "Update failed after %d attempts. Last error: %s",
                            self.retry_count,
                            last_error,
                        )
                        raise UpdateFailed(
                            f"Failed after {self.retry_count} attempts: {last_error}"
                        ) from err

            return None
