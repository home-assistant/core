"""Example integration using DataUpdateCoordinator."""

from datetime import datetime, timedelta
import logging

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from . import mawaqit_wrapper, utils
from .const import CONF_UUID, MAWAQIT_STORAGE_KEY, MAWAQIT_STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class MosqueCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch mosque information."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        """Initialize the mosque coordinator."""
        self.hass = hass
        self.mosque_uuid = config_entry.data.get(CONF_UUID)
        self.token = config_entry.data.get(CONF_API_KEY)

        super().__init__(
            hass,
            _LOGGER,
            name="Mosque Data",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),  # Updated every day
        )

    async def _async_update_data(self):
        """Fetch mosque details from local storage."""
        try:
            mosque_data = await mawaqit_wrapper.fetch_mosque_by_id(
                self.mosque_uuid, token=self.token
            )

        except Exception as err:
            raise UpdateFailed(f"Failed to update mosque data: {err}") from err

        if not mosque_data:
            raise UpdateFailed("No mosque data found")

        return mosque_data


class PrayerTimeCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch prayer times from the Mawaqit API."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        """Initialize the prayer time coordinator."""

        self.hass = hass
        self.store: Store = Store(
            hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY
        )  # Store prayer times locally
        self.mosque_uuid = config_entry.data.get(CONF_UUID)
        self.token = config_entry.data.get(CONF_API_KEY)
        self.last_fetch: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Prayer Times",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self):
        """Fetch prayer times from API, update store, and notify sensors."""

        now = dt_util.utcnow()

        if not self.last_fetch or (now - self.last_fetch) > timedelta(days=1):
            _LOGGER.info("Attempting daily fetch of prayer times from Mawaqit API")

            try:
                # Fetch new data from API
                prayer_times = await mawaqit_wrapper.fetch_prayer_times(
                    mosque=self.mosque_uuid, token=self.token
                )

                if not prayer_times:
                    _LOGGER.error("No prayer times received from API")
                    raise UpdateFailed("No data received from API")

                # Save new data to store
                await utils.write_pray_time(prayer_times, self.store)
                self.last_fetch = now

            except ValueError as err:
                _LOGGER.error("Failed to parse prayer times: %s", err)
            except mawaqit_wrapper.BadCredentialsException as err:
                _LOGGER.error("Bad credentials: %s", err)
                # Handle re-authentication if needed
            except mawaqit_wrapper.NoMosqueAround as err:
                _LOGGER.error("No mosque found in the area: %s", err)
            except mawaqit_wrapper.NoMosqueFound as err:
                _LOGGER.error("No mosque found: %s", err)
            except (ConnectionError, TimeoutError) as err:
                _LOGGER.error("Network-related error: %s", err)

        return await utils.read_pray_time(
            self.store
        )  # Return the cached data for sensors
