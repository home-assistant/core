"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import mawaqit_wrapper, utils
from .const import MAWAQIT_STORAGE_KEY, MAWAQIT_STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class MosqueCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch mosque information."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the mosque coordinator."""
        self.hass = hass
        self.store: Store = Store(hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        super().__init__(
            hass,
            _LOGGER,
            name="Mosque Data",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),  # Static data, updated every 6 hours
        )

    async def _async_update_data(self):
        """Fetch mosque details from local storage."""
        try:
            mosque_data = await utils.read_my_mosque_NN_file(
                self.store
            )  # TODO Fetch directly from the API # pylint: disable=fixme

        except Exception as err:
            raise UpdateFailed(f"Failed to update mosque data: {err}") from err

        if not mosque_data:
            raise UpdateFailed("No mosque data found")

        return mosque_data


class PrayerTimeCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch prayer times from the Mawaqit API."""

    def __init__(self, hass: HomeAssistant, mosque_uuid) -> None:
        """Initialize the prayer time coordinator."""
        self.hass = hass
        self.mosque_uuid = mosque_uuid
        self.store: Store = Store(
            hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY
        )  # Store prayer times locally

        super().__init__(
            hass,
            _LOGGER,
            name="Prayer Times",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),  # Fetch API data every day
        )

    async def _async_update_data(self):
        """Fetch prayer times from API, update store, and notify sensors."""
        try:
            # Fetch new data from API
            user_token = await utils.read_mawaqit_token(None, self.store)
            prayer_times = await mawaqit_wrapper.fetch_prayer_times(
                mosque=self.mosque_uuid, token=user_token
            )

        except Exception as err:
            raise UpdateFailed(f"Failed to update prayer times: {err}") from err

        if not prayer_times:
            _LOGGER.error("No prayer times received from API")
            raise UpdateFailed("No data received from API")

        _LOGGER.info("Fetched new prayer times from API: %s", prayer_times)

        # Save new data to store
        await utils.write_pray_time(prayer_times, self.store)

        return prayer_times  # Return updated data for sensors
